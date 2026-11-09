import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import './Studio3DViewer.css';

export type Studio3DViewerProps = {
  /** Public or signed URL to a .glb/.gltf model. Leave empty to show the studio stage. */
  modelUrl?: string | null;
  /** Bearer token for authenticated immutable AssetVersion content fetches. */
  accessToken?: string;
  /** Optional accessible label for the 3D viewport. */
  label?: string;
  /** Initial stage background color. */
  background?: string;
  /** Show a floor grid for spatial orientation. */
  showGrid?: boolean;
  /** Automatically play embedded glTF animation clips when present. */
  autoPlay?: boolean;
  /** Called when a GLTF/GLB model has loaded and been added to the scene. */
  onLoad?: (model: THREE.Object3D) => void;
  /** Called for model-load failures; raw URLs and server details are not rendered in the UI. */
  onError?: (message: string) => void;
};

type CameraSnapshot = { position: THREE.Vector3; target: THREE.Vector3 };

import { ModelDownloadError, getHttpDownloadError, readModelResponse } from './boundedModelDownload.mjs';
import { resolveModelBasePath } from './modelBasePath.mjs';
import { disposeGltfResources } from './disposeGltfResources.mjs';
import { finalizeGltfLoad } from './finalizeGltfLoad.mjs';
import { reportGltfParseError } from './reportGltfParseError.mjs';
import { disposeViewerResources } from './disposeViewerResources.mjs';
import { runViewerCleanupSteps } from './runViewerCleanupSteps.mjs';
import { notifyViewerError } from './notifyViewerError.mjs';
import { createResourceRollback } from './resourceRollback.mjs';
import { createAnimationFrameController } from './animationFrameController.mjs';
import { attachWebGLContextLifecycle, disposeWebGLContextLifecycleWithRetry } from './webglContextLifecycle.mjs';
import { KeyedRequestGate } from './keyedRequestGate.mjs';

function getModelErrorMessage(error: unknown): string {
  if (error instanceof ModelDownloadError) {
    switch (error.code) {
      case 'unauthorized': return '로그인이 만료되었습니다. 다시 로그인한 뒤 모델을 불러와 주세요.';
      case 'forbidden': return '이 모델을 볼 권한이 없습니다. 프로젝트 또는 에셋 접근 권한을 확인하세요.';
      case 'not_found': return '요청한 모델 버전을 찾을 수 없습니다. 최신 버전을 다시 선택해 주세요.';
      case 'conflict': return '모델 버전 상태가 변경되었습니다. 버전 목록을 새로고침한 뒤 다시 시도해 주세요.';
      case 'too_large': return '모델 파일이 현재 뷰어의 다운로드 한도(256 MiB)를 초과합니다.';
      case 'memory': return '기기의 사용 가능한 메모리가 부족합니다. 다른 앱을 닫거나 더 작은 모델을 사용해 주세요.';
      case 'invalid_body': return '브라우저가 모델 파일을 안전하게 읽을 수 없습니다. 최신 브라우저에서 다시 시도해 주세요.';
      case 'network': return '네트워크 연결을 확인한 뒤 다시 시도해 주세요.';
      default: return '모델 서버에서 파일을 가져오지 못했습니다. 잠시 후 다시 시도해 주세요.';
    }
  }
  return '모델 파일을 해석하지 못했습니다. 파일 형식과 내부 리소스를 확인해 주세요.';
}




/** Real WebGL/Three.js viewer; this is not a CSS perspective or rotateY mock. */
export default function Studio3DViewer({
  modelUrl,
  accessToken,
  label = '3D model viewer',
  background = '#171a21',
  showGrid = true,
  autoPlay = true,
  onLoad,
  onError,
}: Studio3DViewerProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const modelRef = useRef<THREE.Object3D | null>(null);
  const gltfRef = useRef<unknown>(null);
  const homeRef = useRef<CameraSnapshot | null>(null);
  const gridRef = useRef<THREE.GridHelper | null>(null);
  const stageGroupRef = useRef<THREE.Group | null>(null);
  const keyLightRef = useRef<THREE.DirectionalLight | null>(null);
  const mixerRef = useRef<THREE.AnimationMixer | null>(null);
  const clockRef = useRef<THREE.Clock | null>(null);
  const [hasAnimations, setHasAnimations] = useState(false);
  const [animationPlaying, setAnimationPlaying] = useState(autoPlay);
  const animationPlayingRef = useRef(autoPlay);
  const [loadState, setLoadState] = useState<'stage' | 'loading' | 'ready' | 'error'>('stage');
  const [contextLost, setContextLost] = useState(false);
  const [errorMessage, setErrorMessage] = useState('모델을 표시할 수 없습니다.');
  const [progress, setProgress] = useState(0);
  const [gridVisible, setGridVisible] = useState(showGrid);
  const [sceneVersion, setSceneVersion] = useState(0);
  const onLoadRef = useRef(onLoad);
  const onErrorRef = useRef(onError);
  // A monotonically increasing owner token protects every asynchronous model
  // completion path, including the non-abortable GLTF parser callbacks.
  const modelRequestGateRef = useRef(new KeyedRequestGate());

  useEffect(() => { onLoadRef.current = onLoad; }, [onLoad]);
  useEffect(() => { onErrorRef.current = onError; }, [onError]);

  useEffect(() => setGridVisible(showGrid), [showGrid]);
  useEffect(() => {
    animationPlayingRef.current = autoPlay;
    setAnimationPlaying(autoPlay);
  }, [autoPlay]);
  useEffect(() => { animationPlayingRef.current = animationPlaying; }, [animationPlaying]);
  useEffect(() => {
    const mixer = mixerRef.current;
    if (!mixer) return;
    if (animationPlaying) mixer.timeScale = 1;
    else mixer.timeScale = 0;
  }, [animationPlaying]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;

    setContextLost(false);
    const rollback = createResourceRollback();
    rollback.defer('clear-viewer-references', () => {
      mixerRef.current = null;
      clockRef.current = null;
      gltfRef.current = null;
      stageGroupRef.current = null;
      keyLightRef.current = null;
      controlsRef.current = null;
      cameraRef.current = null;
      sceneRef.current = null;
      modelRef.current = null;
      gridRef.current = null;
    });
    try {
        const scene = new THREE.Scene();
        rollback.defer('dispose-scene-resources', () => disposeViewerResources(scene));
        scene.background = new THREE.Color(background);
        sceneRef.current = scene;
        setSceneVersion((version) => version + 1);

        const camera = new THREE.PerspectiveCamera(42, 1, 0.01, 1000);
        camera.position.set(3.8, 2.6, 5.2);
        cameraRef.current = camera;

        // WebGLRenderer construction can throw when WebGL is unavailable, the
        // browser has exhausted its context quota, or GPU initialization fails.
        // Treat this as a recoverable viewer state instead of letting the React
        // effect fail before it can register a cleanup function.
        let renderer: THREE.WebGLRenderer;
        try {
          renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'high-performance' });
          rollback.defer('dispose-webgl-renderer', () => renderer.dispose());
        } catch {
          rollback.rollback(({ errors }) => {
            try { console.error('[AI CREATOR STUDIO] 3D renderer rollback errors', errors); } catch { /* Diagnostics are best-effort. */ }
          });
          const message = '이 브라우저에서 3D 그래픽을 초기화할 수 없습니다. WebGL 지원 여부와 그래픽 드라이버 상태를 확인해 주세요.';
          setErrorMessage(message);
          setLoadState('error');
          notifyViewerError(onErrorRef.current, message);
          return;
        }
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
        renderer.outputColorSpace = THREE.SRGBColorSpace;
        renderer.toneMapping = THREE.ACESFilmicToneMapping;
        renderer.toneMappingExposure = 1.05;
        renderer.shadowMap.enabled = true;
        renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        renderer.domElement.className = 'acs-3d-canvas';
        renderer.domElement.setAttribute('aria-label', label);
        renderer.domElement.setAttribute('role', 'img');
        host.prepend(renderer.domElement);
        rollback.defer('remove-renderer-canvas', () => renderer.domElement.remove());

        scene.add(new THREE.HemisphereLight(0xeaf1ff, 0x38313a, 2.1));
        const keyLight = new THREE.DirectionalLight(0xfff2df, 3.0);
        keyLightRef.current = keyLight;
        rollback.defer('dispose-key-light-shadow', () => keyLight.shadow.dispose());
        keyLight.position.set(4, 7, 5);
        keyLight.castShadow = true;
        keyLight.shadow.mapSize.set(1024, 1024);
        scene.add(keyLight);
        const fillLight = new THREE.DirectionalLight(0xb9d7ff, 1.25);
        fillLight.position.set(-5, 3, -3);
        scene.add(fillLight);

        const stageGroup = new THREE.Group();
        stageGroup.name = 'acs-stage-resources';
        stageGroupRef.current = stageGroup;
        scene.add(stageGroup);

        const floorGeometry = new THREE.PlaneGeometry(200, 200);
        const disposeFloorGeometry = () => floorGeometry.dispose();
        rollback.defer('dispose-unattached-floor-geometry', disposeFloorGeometry);
        const floorMaterial = new THREE.MeshStandardMaterial({ color: '#242832', roughness: 0.92, metalness: 0.02 });
        const disposeFloorMaterial = () => floorMaterial.dispose();
        rollback.defer('dispose-unattached-floor-material', disposeFloorMaterial);
        const floor = new THREE.Mesh(floorGeometry, floorMaterial);
        floor.rotation.x = -Math.PI / 2;
        floor.position.y = -0.015;
        floor.receiveShadow = true;
        floor.name = 'acs-stage-floor';
        stageGroup.add(floor);
        rollback.release(disposeFloorGeometry);
        rollback.release(disposeFloorMaterial);

        const grid = new THREE.GridHelper(12, 24, 0x596273, 0x343b49);
        grid.position.y = 0.002;
        grid.visible = gridVisible;
        gridRef.current = grid;
        stageGroup.add(grid);

        const controls = new OrbitControls(camera, renderer.domElement);
        // OrbitControls installs DOM listeners in its constructor. Register its
        // disposer immediately, before any configuration or update can throw.
        rollback.defer('dispose-orbit-controls', () => controls.dispose());
        controls.enableDamping = true;
        controls.dampingFactor = 0.075;
        controls.minDistance = 0.15;
        controls.maxDistance = 80;
        controls.maxPolarAngle = Math.PI * 0.495;
        controls.target.set(0, 1, 0);
        controls.update();
        controlsRef.current = controls;
        homeRef.current = { position: camera.position.clone(), target: controls.target.clone() };

        let disposed = false;
        const clock = new THREE.Clock();
        clockRef.current = clock;
        const resize = () => {
          const width = Math.max(host.clientWidth, 1);
          const height = Math.max(host.clientHeight, 1);
          camera.aspect = width / height;
          camera.updateProjectionMatrix();
          renderer.setSize(width, height, false);
        };
        const observer = new ResizeObserver(resize);
        rollback.defer('disconnect-resize-observer', () => observer.disconnect());
        observer.observe(host);
        resize();

        const animationLoop = createAnimationFrameController({
          requestFrame: (callback) => window.requestAnimationFrame(callback),
          cancelFrame: (frameId) => window.cancelAnimationFrame(frameId),
          render: () => {
            if (disposed) return;
            controls.update();
            mixerRef.current?.update(clock.getDelta());
            renderer.render(scene, camera);
          },
          onError: () => {
            const message = '3D 화면을 렌더링하지 못했습니다. 그래픽 드라이버 또는 브라우저의 WebGL 상태를 확인해 주세요.';
            setErrorMessage(message);
            setLoadState('error');
            notifyViewerError(onErrorRef.current, message);
          },
        });
        const contextLifecycle = attachWebGLContextLifecycle({
          canvas: renderer.domElement,
          animationLoop,
          clock,
          resize,
          onLost: () => setContextLost(true),
          onRestored: () => setContextLost(false),
          onError: () => {
            const message = '그래픽 컨텍스트를 복구하지 못했습니다. 페이지를 새로고침하거나 그래픽 드라이버 상태를 확인해 주세요.';
            setErrorMessage(message);
            setLoadState('error');
            notifyViewerError(onErrorRef.current, message);
          },
        });
        rollback.defer('remove-webgl-context-listeners', () => {
          if (!disposeWebGLContextLifecycleWithRetry(contextLifecycle, 2)) {
            throw new Error('WebGL context listeners could not be fully removed after 2 attempts');
          }
        });
        rollback.defer('cancel-animation-frame', () => animationLoop.stop());
        animationLoop.start();

        rollback.commit();
        return () => {
          disposed = true;
          const mixer = mixerRef.current;
          runViewerCleanupSteps([
            { name: 'cancel-animation-frame', run: () => animationLoop.stop() },
            { name: 'disconnect-resize-observer', run: () => observer.disconnect() },
            { name: 'remove-webgl-context-listeners', run: () => {
              if (!disposeWebGLContextLifecycleWithRetry(contextLifecycle, 2)) {
                throw new Error('WebGL context listeners could not be fully removed after 2 attempts');
              }
            } },
            { name: 'dispose-orbit-controls', run: () => controls.dispose() },
            { name: 'stop-animation-actions', run: () => mixer?.stopAllAction() },
            { name: 'uncache-animation-root', run: () => { if (mixer && modelRef.current) mixer.uncacheRoot(modelRef.current); } },
            { name: 'dispose-loaded-gltf', run: () => disposeViewerResources(gltfRef.current) },
            { name: 'dispose-stage-resources', run: () => disposeViewerResources(stageGroupRef.current) },
            { name: 'dispose-key-light-shadow', run: () => keyLightRef.current?.shadow.dispose() },
            { name: 'dispose-webgl-renderer', run: () => renderer.dispose() },
            { name: 'remove-renderer-canvas', run: () => renderer.domElement.remove() },
            { name: 'clear-viewer-references', run: () => {
              mixerRef.current = null;
              clockRef.current = null;
              gltfRef.current = null;
              stageGroupRef.current = null;
              keyLightRef.current = null;
              controlsRef.current = null;
              cameraRef.current = null;
              sceneRef.current = null;
              modelRef.current = null;
              gridRef.current = null;
            } },
          ], ({ errors }) => {
            try { console.error('[AI CREATOR STUDIO] 3D viewer teardown errors', errors); } catch { /* Cleanup diagnostics are best-effort. */ }
          });
        };
    } catch (error) {
      const rollbackResult = rollback.rollback(({ errors }) => {
        try { console.error('[AI CREATOR STUDIO] 3D viewer setup rollback errors', errors); } catch { /* Diagnostics are best-effort. */ }
      });
      const message = '3D 뷰어를 초기화하지 못했습니다. 브라우저의 WebGL 지원 여부와 그래픽 드라이버 상태를 확인해 주세요.';
      setErrorMessage(message);
      setLoadState('error');
      try {
        notifyViewerError(onErrorRef.current, message);
      } catch { /* Error notification must not mask the original setup failure. */ }
      try {
        console.error('[AI CREATOR STUDIO] 3D viewer setup failed', error, rollbackResult);
      } catch { /* Diagnostics are best-effort. */ }
      return;
    }
    // grid visibility is synchronized separately so toggling it doesn't recreate WebGL.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [background, label]);

  useEffect(() => {
    const grid = gridRef.current;
    if (grid) grid.visible = gridVisible;
  }, [gridVisible]);

  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene || sceneVersion === 0) return;

    const previousModel = modelRef.current;
    const previousMixer = mixerRef.current;
    const previousGltf = gltfRef.current;
    runViewerCleanupSteps([
      { name: 'remove-previous-model', run: () => { if (previousModel) scene.remove(previousModel); } },
      { name: 'stop-previous-animation', run: () => previousMixer?.stopAllAction() },
      { name: 'uncache-previous-animation-root', run: () => { if (previousMixer && previousModel) previousMixer.uncacheRoot(previousModel); } },
      { name: 'dispose-previous-gltf', run: () => previousGltf ? disposeViewerResources(previousGltf) : previousModel ? disposeViewerResources(previousModel) : undefined },
      { name: 'clear-previous-model-references', run: () => { mixerRef.current = null; gltfRef.current = null; modelRef.current = null; } },
    ], ({ errors }) => {
      try { console.error('[AI CREATOR STUDIO] previous model cleanup errors', errors); } catch { /* Cleanup diagnostics are best-effort. */ }
    });
    setHasAnimations(false);

    if (!modelUrl) {
      setLoadState('stage');
      setProgress(0);
      return;
    }

    const requestId = modelRequestGateRef.current.next('model');
    const isCurrentRequest = () => modelRequestGateRef.current.isCurrent('model', requestId);
    setLoadState('loading');
    setErrorMessage('모델을 표시할 수 없습니다.');
    setProgress(0);
    const loader = new GLTFLoader();
    const controller = new AbortController();
    const parseModel = (bytes: ArrayBuffer) => loader.parse(
      bytes,
      resolveModelBasePath(modelUrl, window.location.href),
      (gltf) => {
        const model = gltf.scene;
        const outcome = finalizeGltfLoad({
          gltf,
          cancelled: !isCurrentRequest(),
          commit: () => {
            gltfRef.current = gltf;
            model.traverse((object) => {
              const mesh = object as THREE.Mesh;
              if (mesh.isMesh) {
                mesh.castShadow = true;
                mesh.receiveShadow = true;
              }
            });
            const bounds = new THREE.Box3().setFromObject(model);
            const size = bounds.getSize(new THREE.Vector3());
            const center = bounds.getCenter(new THREE.Vector3());
            if (size.length() > 0) {
              model.position.sub(center);
              const normalizedBounds = new THREE.Box3().setFromObject(model);
              model.position.y -= normalizedBounds.min.y;
            }
            scene.add(model);
            modelRef.current = model;
            if (gltf.animations.length > 0) {
              const mixer = new THREE.AnimationMixer(model);
              // Publish ownership before clip setup so a partial animation setup
              // failure is included in the GLTF commit rollback.
              mixerRef.current = mixer;
              gltf.animations.forEach((clip) => mixer.clipAction(clip).play());
              mixer.timeScale = animationPlayingRef.current ? 1 : 0;
              setHasAnimations(true);
            } else {
              setHasAnimations(false);
            }

            const fittedBounds = new THREE.Box3().setFromObject(model);
            const fittedSize = fittedBounds.getSize(new THREE.Vector3());
            const maxDimension = Math.max(fittedSize.x, fittedSize.y, fittedSize.z, 1);
            const camera = cameraRef.current;
            const controls = controlsRef.current;
            if (camera && controls) {
              controls.target.set(0, fittedSize.y * 0.48, 0);
              camera.position.set(maxDimension * 1.5, maxDimension * 0.95, maxDimension * 1.8);
              camera.near = Math.max(maxDimension / 1000, 0.001);
              camera.far = Math.max(maxDimension * 100, 100);
              camera.updateProjectionMatrix();
              controls.update();
              homeRef.current = { position: camera.position.clone(), target: controls.target.clone() };
            }
          },
          rollback: (failedGltf) => {
            const failedModel = failedGltf.scene;
            try { scene.remove(failedModel); } catch { /* Continue resource rollback. */ }
            const failedMixer = mixerRef.current;
            if (failedMixer && modelRef.current === failedModel) {
              try { failedMixer.stopAllAction(); } catch { /* Best-effort animation rollback. */ }
              try { failedMixer.uncacheRoot(failedModel); } catch { /* Best-effort animation rollback. */ }
              mixerRef.current = null;
            }
            if (modelRef.current === failedModel) modelRef.current = null;
            if (gltfRef.current === failedGltf) gltfRef.current = null;
            disposeGltfResources(failedGltf);
          },
        });
        if (outcome.status === 'cancelled') {
          if (outcome.cleanupError) {
            try { console.error('[AI CREATOR STUDIO] cancelled GLTF cleanup failed', outcome.cleanupError); } catch { /* Diagnostics are best-effort. */ }
          }
          return;
        }
        if (outcome.status === 'failed') {
          const message = '모델을 장면에 적용하지 못했습니다. 모델 파일을 다시 확인해 주세요.';
          setErrorMessage(message);
          setLoadState('error');
          notifyViewerError(onErrorRef.current, message);
          try { console.error('[AI CREATOR STUDIO] GLTF commit failed', outcome.error, outcome.cleanupError); } catch { /* Diagnostics are best-effort. */ }
          return;
        }
        setProgress(100);
        setLoadState('ready');
        try {
          onLoadRef.current?.(model);
        } catch (callbackError) {
          // Consumer callbacks must not corrupt a successfully committed scene.
          try { console.error('[AI CREATOR STUDIO] onLoad callback failed', callbackError); } catch { /* Diagnostics are best-effort. */ }
        }
      },
      () => {
        // GLTFLoader.parse is not abortable. Its error callback can therefore
        // arrive after a newer model has replaced this request or the viewer
        // has unmounted. The shared guard makes this race directly testable.
        reportGltfParseError({
          cancelled: !isCurrentRequest(),
          message: '모델 파일을 해석하지 못했습니다. 파일 형식과 내부 리소스를 확인해 주세요.',
          setErrorMessage,
          setLoadState,
          notifyError: (message) => notifyViewerError(onErrorRef.current, message),
        });
      },
    );
    // Private models are fetched with the current access token. The upload
    // validator rejects external glTF URIs, so GLB and data-URI glTF resources
    // can be parsed without issuing unauthenticated secondary network requests.
    fetch(modelUrl, {
      method: 'GET',
      headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined,
      cache: 'no-store',
      signal: controller.signal,
    }).then(async (response) => {
      if (!response.ok) throw getHttpDownloadError(response.status);
      const bytes = await readModelResponse(response, controller.signal, setProgress);
      if (!isCurrentRequest()) return;
      setProgress(98);
      parseModel(bytes);
    }).catch((error: unknown) => {
      if (!isCurrentRequest() || (error instanceof DOMException && error.name === 'AbortError')) return;
      const message = getModelErrorMessage(error);
      setErrorMessage(message);
      setLoadState('error');
      notifyViewerError(onErrorRef.current, message);
    });
    return () => {
      // Invalidate synchronously before aborting the fetch. GLTFLoader.parse
      // cannot be aborted, so its late success/error callbacks must fail the
      // same owner check as fetch completions.
      modelRequestGateRef.current.invalidate('model');
      controller.abort();
    };
  }, [modelUrl, accessToken, sceneVersion]);

  const resetCamera = () => {
    const camera = cameraRef.current;
    const controls = controlsRef.current;
    const home = homeRef.current;
    if (!camera || !controls || !home) return;
    camera.position.copy(home.position);
    controls.target.copy(home.target);
    controls.update();
  };

  return (
    <section className="acs-3d-viewer" aria-label={label}>
      <div className="acs-3d-viewport" ref={hostRef}>
        {contextLost && (
          <div className="acs-3d-status acs-3d-error" role="alert">
            <strong>그래픽 컨텍스트가 일시 중단되었습니다</strong>
            <span>브라우저가 WebGL을 복구하는 동안 렌더링을 중지했습니다. 복구되면 자동으로 다시 표시됩니다.</span>
          </div>
        )}
        {loadState === 'loading' && (
          <div className="acs-3d-status" role="status">
            <span className="acs-3d-spinner" />
            <strong>3D 모델 불러오는 중</strong>
            <span>{progress > 0 ? `${progress}%` : '잠시만 기다려 주세요'}</span>
          </div>
        )}
        {loadState === 'error' && (
          <div className="acs-3d-status acs-3d-error" role="alert">
            <strong>모델을 표시할 수 없습니다</strong>
            <span>{errorMessage}</span>
          </div>
        )}
        {loadState === 'stage' && (
          <div className="acs-3d-stage-hint">GLB/GLTF 모델을 연결하면 이 공간에서 회전·확대해 볼 수 있습니다.</div>
        )}
        <div className="acs-3d-toolbar" aria-label="3D viewer controls">
          <button type="button" onClick={resetCamera}>시점 초기화</button>
          <button type="button" aria-pressed={gridVisible} onClick={() => setGridVisible((visible) => !visible)}>
            바닥 격자 {gridVisible ? '끄기' : '켜기'}
          </button>
          {hasAnimations && (
            <button type="button" aria-pressed={animationPlaying} onClick={() => setAnimationPlaying((playing) => !playing)}>
              애니메이션 {animationPlaying ? '일시정지' : '재생'}
            </button>
          )}
        </div>
        <div className="acs-3d-help">드래그: 회전 · 휠: 확대/축소 · 우클릭 드래그: 이동</div>
      </div>
    </section>
  );
}
