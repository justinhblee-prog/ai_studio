import { ChangeEvent, FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import './ProductCatalogWorkspace.css';
import { useRequestScope } from './useRequestScope';

type ImageAsset = { asset_id: string; original_filename: string };
type Product = {
  product_id: string;
  workspace_id: string;
  sku: string;
  name: string;
  description: string | null;
  category: string;
  created_by: string;
  created_at: string;
  archived_at?: string | null;
  status: 'active' | 'archived';
  image_asset_ids: string[];
  variants: ProductVariant[];
  updated_at: string;
};
type ProductVariant = { variant_id: string; product_id: string; workspace_id: string; sku: string; option_values: Record<string, string>; image_asset_ids: string[]; status: 'active' | 'archived'; created_by: string; created_at: string; updated_at: string; archived_at?: string | null };

export type ProductCatalogWorkspaceProps = {
  apiBaseUrl: string;
  accessToken: string;
  workspaceId: string;
};

async function responseError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    const detail = body?.detail;
    return typeof detail === 'string' ? detail : detail?.message || `요청 실패 (${response.status})`;
  } catch {
    return `요청 실패 (${response.status})`;
  }
}

export function ProductCatalogWorkspace({ apiBaseUrl, accessToken, workspaceId }: ProductCatalogWorkspaceProps) {
  const base = apiBaseUrl.replace(/\/$/, '');
  const headers = { Authorization: `Bearer ${accessToken}` };
  const { capture: captureScope, isCurrent: isScopeCurrent } = useRequestScope([base, accessToken, workspaceId]);
  const [images, setImages] = useState<ImageAsset[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const loadSequenceRef = useRef(0);
  const requestScopeRef = useRef({ workspaceId, accessToken });
  requestScopeRef.current = { workspaceId, accessToken };
  const [sku, setSku] = useState('');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState('apparel');
  const [editingProductId, setEditingProductId] = useState('');
  const [imageAssetIds, setImageAssetIds] = useState<string[]>([]);
  const [variantParentId, setVariantParentId] = useState('');
  const [variantSku, setVariantSku] = useState('');
  const [variantColor, setVariantColor] = useState('');
  const [variantSize, setVariantSize] = useState('');
  const [variantImageAssetIds, setVariantImageAssetIds] = useState<string[]>([]);
  const [variantExtraOptions, setVariantExtraOptions] = useState<Record<string, string>>({});
  const [newOptionKey, setNewOptionKey] = useState('');
  const [newOptionValue, setNewOptionValue] = useState('');
  const [editingVariantId, setEditingVariantId] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    const requestId = ++loadSequenceRef.current;
    const [imageResponse, productResponse] = await Promise.all([
      fetch(`${base}/v1/assets?workspace_id=${encodeURIComponent(workspaceId)}&kind=image`, { headers, signal }),
      fetch(`${base}/v1/products?workspace_id=${encodeURIComponent(workspaceId)}&limit=100`, { headers, signal }),
    ]);
    if (!imageResponse.ok) throw new Error(await responseError(imageResponse));
    if (!productResponse.ok) throw new Error(await responseError(productResponse));
    const imageResult = await imageResponse.json() as { items: ImageAsset[] };
    const productResult = await productResponse.json() as { items: Product[] };
    if (requestId !== loadSequenceRef.current || requestScopeRef.current.workspaceId !== workspaceId || requestScopeRef.current.accessToken !== accessToken) return;
    setImages(imageResult.items);
    setProducts(productResult.items);
    setImageAssetIds((current) => current.filter((id) => imageResult.items.some((image) => image.asset_id === id)));
    setVariantImageAssetIds((current) => current.filter((id) => imageResult.items.some((image) => image.asset_id === id)));
  }, [base, accessToken, workspaceId]);

  useEffect(() => {
    setImages([]); setProducts([]); setError(null); setBusy(false);
    setEditingProductId(''); setSku(''); setName(''); setDescription(''); setCategory('apparel'); setImageAssetIds([]);
    setVariantParentId(''); setEditingVariantId(''); setVariantSku(''); setVariantColor(''); setVariantSize('');
    setVariantImageAssetIds([]); setVariantExtraOptions({}); setNewOptionKey(''); setNewOptionValue('');
  }, [base, accessToken, workspaceId]);

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal).catch((reason: unknown) => {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : '상품 카탈로그를 불러오지 못했습니다.');
    });
    return () => controller.abort();
  }, [load]);

  const clearProductForm = useCallback(() => {
    setEditingProductId(''); setSku(''); setName(''); setDescription(''); setCategory('apparel'); setImageAssetIds([]);
  }, []);

  const startProductEdit = useCallback((product: Product) => {
    setEditingProductId(product.product_id);
    setSku(product.sku);
    setName(product.name);
    setDescription(product.description || '');
    setCategory(product.category);
    setImageAssetIds(product.image_asset_ids);
  }, []);

  const saveProduct = useCallback(async (event: FormEvent<HTMLFormElement>) => {
    const scope = captureScope();
    event.preventDefault();
    if (imageAssetIds.length === 0 || imageAssetIds.length > 12) return;
    setBusy(true);
    setError(null);
    try {
      const headersWithJson = { ...headers, 'Content-Type': 'application/json' };
      const response = editingProductId
        ? await fetch(`${base}/v1/products/${encodeURIComponent(editingProductId)}`, {
            method: 'PUT', headers: headersWithJson,
            body: JSON.stringify({ workspace_id: workspaceId, sku: sku.trim(), name: name.trim(), description: description.trim() || null, category: category.trim(), image_asset_ids: imageAssetIds }),
          })
        : await fetch(`${base}/v1/products`, {
            method: 'POST', headers: headersWithJson,
            body: JSON.stringify({ workspace_id: workspaceId, sku: sku.trim(), name: name.trim(), description: description.trim() || null, category: category.trim(), image_asset_ids: imageAssetIds }),
          });
      if (!response.ok) throw new Error(await responseError(response));
      if (!isScopeCurrent(scope)) return;
      clearProductForm();
      await load();
    } catch (reason) {
      if (isScopeCurrent(scope)) setError(reason instanceof Error ? reason.message : '상품을 저장하지 못했습니다.');
    } finally {
      if (isScopeCurrent(scope)) setBusy(false);
    }
  }, [base, accessToken, workspaceId, editingProductId, sku, name, description, category, imageAssetIds, clearProductForm, load, captureScope, isScopeCurrent]);

  const clearVariantForm = useCallback(() => {
    setVariantParentId(''); setEditingVariantId(''); setVariantSku(''); setVariantColor(''); setVariantSize('');
    setVariantImageAssetIds([]); setVariantExtraOptions({}); setNewOptionKey(''); setNewOptionValue('');
  }, []);

  const archiveProduct = useCallback(async (productId: string) => {
    const scope = captureScope();
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`${base}/v1/products/${encodeURIComponent(productId)}/archive?workspace_id=${encodeURIComponent(workspaceId)}`, { method: 'POST', headers });
      if (!response.ok) throw new Error(await responseError(response));
      if (!isScopeCurrent(scope)) return;
      if (editingProductId === productId) clearProductForm();
      if (variantParentId === productId) clearVariantForm();
      await load();
    } catch (reason) {
      if (isScopeCurrent(scope)) setError(reason instanceof Error ? reason.message : '상품을 보관하지 못했습니다.');
    } finally {
      if (isScopeCurrent(scope)) setBusy(false);
    }
  }, [base, accessToken, workspaceId, editingProductId, variantParentId, clearProductForm, clearVariantForm, load, captureScope, isScopeCurrent]);

  const selectImages = useCallback((event: ChangeEvent<HTMLSelectElement>) => {
    setImageAssetIds(Array.from(event.currentTarget.selectedOptions, (option) => option.value));
  }, []);

  const startVariantEdit = useCallback((productId: string, variant: ProductVariant) => {
    setVariantParentId(productId);
    setEditingVariantId(variant.variant_id);
    setVariantSku(variant.sku);
    setVariantColor(variant.option_values.color || '');
    setVariantSize(variant.option_values.size || '');
    setVariantExtraOptions(Object.fromEntries(Object.entries(variant.option_values).filter(([key]) => key !== 'color' && key !== 'size')));
    setNewOptionKey(''); setNewOptionValue('');
    setVariantImageAssetIds(variant.image_asset_ids);
  }, []);

  const addExtraOption = useCallback(() => {
    const key = newOptionKey.trim().toLowerCase();
    const value = newOptionValue.trim();
    if (!/^[a-z0-9_]{1,40}$/.test(key) || !value || value.length > 80) {
      setError('추가 옵션 키는 영문/숫자/밑줄 1~40자, 값은 1~80자로 입력해 주세요.');
      return;
    }
    if (key === 'color' || key === 'size' || Object.keys(variantExtraOptions).some((existing) => existing.toLowerCase() === key)) {
      setError('color/size 또는 이미 등록된 옵션 키는 사용할 수 없습니다.');
      return;
    }
    if (Object.keys(variantExtraOptions).length + (variantColor.trim() ? 1 : 0) + (variantSize.trim() ? 1 : 0) >= 12) {
      setError('Variant 옵션은 최대 12개까지 등록할 수 있습니다.');
      return;
    }
    setVariantExtraOptions((current) => ({ ...current, [key]: value }));
    setNewOptionKey(''); setNewOptionValue(''); setError(null);
  }, [newOptionKey, newOptionValue, variantExtraOptions, variantColor, variantSize]);

  const saveVariant = useCallback(async (event: FormEvent<HTMLFormElement>) => {
    const scope = captureScope();
    event.preventDefault();
    if (!variantParentId || !variantSku.trim() || (!variantColor.trim() && !variantSize.trim() && Object.keys(variantExtraOptions).length === 0)) return;
    setBusy(true); setError(null);
    try {
      const option_values: Record<string, string> = {};
      for (const [key, rawValue] of Object.entries(variantExtraOptions)) {
        const value = rawValue.trim();
        if (!value || value.length > 80) { setError(`추가 옵션 '${key}'의 값은 1~80자로 입력해 주세요.`); return; }
        option_values[key] = value;
      }
      if (variantColor.trim()) option_values.color = variantColor.trim();
      if (variantSize.trim()) option_values.size = variantSize.trim();
      if (Object.keys(option_values).length > 12) { setError('Variant 옵션은 최대 12개까지 등록할 수 있습니다.'); return; }
      const requestHeaders = { ...headers, 'Content-Type': 'application/json' };
      const response = editingVariantId
        ? await fetch(`${base}/v1/products/${encodeURIComponent(variantParentId)}/variants/${encodeURIComponent(editingVariantId)}`, {
            method: 'PUT', headers: requestHeaders,
            body: JSON.stringify({ workspace_id: workspaceId, sku: variantSku.trim(), option_values, image_asset_ids: variantImageAssetIds }),
          })
        : await fetch(`${base}/v1/products/${encodeURIComponent(variantParentId)}/variants`, {
            method: 'POST', headers: requestHeaders,
            body: JSON.stringify({ workspace_id: workspaceId, sku: variantSku.trim(), option_values, image_asset_ids: variantImageAssetIds }),
          });
      if (!response.ok) throw new Error(await responseError(response));
      if (!isScopeCurrent(scope)) return;
      clearVariantForm();
      await load();
    } catch (reason) {
      if (isScopeCurrent(scope)) setError(reason instanceof Error ? reason.message : '상품 옵션을 저장하지 못했습니다.');
    } finally { if (isScopeCurrent(scope)) setBusy(false); }
  }, [base, accessToken, workspaceId, variantParentId, editingVariantId, variantSku, variantColor, variantSize, variantExtraOptions, variantImageAssetIds, clearVariantForm, load, captureScope, isScopeCurrent]);

  const archiveVariant = useCallback(async (productId: string, variantId: string) => {
    const scope = captureScope();
    setBusy(true); setError(null);
    try {
      const response = await fetch(`${base}/v1/products/${encodeURIComponent(productId)}/variants/${encodeURIComponent(variantId)}/archive?workspace_id=${encodeURIComponent(workspaceId)}`, { method: 'POST', headers });
      if (!response.ok) throw new Error(await responseError(response));
      if (!isScopeCurrent(scope)) return;
      if (editingVariantId === variantId) clearVariantForm();
      await load();
    } catch (reason) { if (isScopeCurrent(scope)) setError(reason instanceof Error ? reason.message : '상품 옵션을 보관하지 못했습니다.'); }
    finally { if (isScopeCurrent(scope)) setBusy(false); }
  }, [base, accessToken, workspaceId, editingVariantId, clearVariantForm, load, captureScope, isScopeCurrent]);

  return (
    <section className="acs-product-catalog" aria-label="상품 SKU 카탈로그">
      <header><div><strong>상품 SKU 카탈로그</strong><span>Lookbook에 연결할 상품과 이미지 관리</span></div></header>
      <p className="acs-product-notice">SKU는 Workspace 안에서 대소문자를 구분하지 않고 고유합니다. 상품 보관은 기록을 유지하며, 활성 Lookbook 초안에서 사용 중인 상품은 먼저 초안을 보관해야 합니다.</p>
      {error && <p className="acs-product-error" role="alert">{error}</p>}
      <div className="acs-product-grid">
        <form onSubmit={saveProduct}>
          <label>SKU<input value={sku} maxLength={64} onChange={(event) => setSku(event.currentTarget.value)} placeholder="예: JACKET-001" disabled={busy} required /></label>
          <label>상품명<input value={name} maxLength={160} onChange={(event) => setName(event.currentTarget.value)} disabled={busy} required /></label>
          <label>설명<input value={description} maxLength={2000} onChange={(event) => setDescription(event.currentTarget.value)} disabled={busy} /></label>
          <label>카테고리<input value={category} maxLength={64} onChange={(event) => setCategory(event.currentTarget.value)} disabled={busy} /></label>
          <label>상품 이미지<select multiple size={5} value={imageAssetIds} onChange={selectImages} disabled={busy || images.length === 0} required>
            {images.map((image) => <option key={image.asset_id} value={image.asset_id}>{image.original_filename}</option>)}
          </select><small>{imageAssetIds.length}개 선택 · 최대 12개</small></label>
          <button type="submit" disabled={busy || imageAssetIds.length === 0 || imageAssetIds.length > 12}>{editingProductId ? '상품 변경 저장' : '상품 등록'}</button>
          {editingProductId && <button type="button" disabled={busy} onClick={clearProductForm}>편집 취소</button>}
        </form>
        <section className="acs-product-list" aria-label="등록된 상품">
          <header><strong>등록된 상품</strong><span>{products.length}개</span></header>
          {products.map((product) => <article key={product.product_id} className="acs-product-item">
            <div><strong>{product.sku} · {product.name}</strong><span>{product.category} · 이미지 {product.image_asset_ids.length}개</span>{product.description && <small>{product.description}</small>}
              <div className="acs-product-variants"><strong>옵션 / Variant</strong>
                {product.variants.filter((variant) => variant.status === 'active').map((variant) => <span key={variant.variant_id}>{variant.sku} · {Object.entries(variant.option_values).map(([key, value]) => `${key}: ${value}`).join(' / ')} · {variant.image_asset_ids.length ? `전용 이미지 ${variant.image_asset_ids.length}개` : '상품 이미지 사용'} <button type="button" disabled={busy} onClick={() => startVariantEdit(product.product_id, variant)}>옵션 편집</button><button type="button" disabled={busy} onClick={() => archiveVariant(product.product_id, variant.variant_id)}>옵션 보관</button></span>)}
                <button type="button" disabled={busy} onClick={() => { if (variantParentId === product.product_id) clearVariantForm(); else { clearVariantForm(); setVariantParentId(product.product_id); } }}>{variantParentId === product.product_id ? '옵션 폼 닫기' : '옵션 추가'}</button>
                {variantParentId === product.product_id && <form className="acs-product-variant-form" onSubmit={saveVariant}>
                  <strong>{editingVariantId ? 'Variant 편집' : '새 Variant'}</strong>
                  <input aria-label="Variant SKU" value={variantSku} maxLength={64} placeholder="예: STYLE-001-BLK-M" onChange={(event) => setVariantSku(event.currentTarget.value)} required disabled={busy} />
                  <input aria-label="색상" value={variantColor} maxLength={80} placeholder="색상 (선택)" onChange={(event) => setVariantColor(event.currentTarget.value)} disabled={busy} />
                  <input aria-label="사이즈" value={variantSize} maxLength={80} placeholder="사이즈 (선택)" onChange={(event) => setVariantSize(event.currentTarget.value)} disabled={busy} />
                  <div className="acs-product-extra-options" aria-label="추가 Variant 옵션">
                    <strong>추가 옵션</strong>
                    {Object.entries(variantExtraOptions).map(([key, value]) => <div key={key}>
                      <label>{key}<input aria-label={`${key} 옵션 값`} value={value} maxLength={80} required disabled={busy} onChange={(event) => setVariantExtraOptions((current) => ({ ...current, [key]: event.currentTarget.value }))} /></label>
                      <button type="button" disabled={busy} onClick={() => setVariantExtraOptions((current) => { const next = { ...current }; delete next[key]; return next; })}>삭제</button>
                    </div>)}
                    <div className="acs-product-add-option">
                      <input aria-label="추가 옵션 키" value={newOptionKey} maxLength={40} placeholder="예: material" onChange={(event) => setNewOptionKey(event.currentTarget.value)} disabled={busy} />
                      <input aria-label="추가 옵션 값" value={newOptionValue} maxLength={80} placeholder="예: cotton" onChange={(event) => setNewOptionValue(event.currentTarget.value)} disabled={busy} />
                      <button type="button" disabled={busy || !newOptionKey.trim() || !newOptionValue.trim() || Object.keys(variantExtraOptions).length + (variantColor.trim() ? 1 : 0) + (variantSize.trim() ? 1 : 0) >= 12} onClick={addExtraOption}>옵션 추가</button>
                    </div>
                    <small>예: 소재, 핏, 패턴, 길이 등. 키는 영문·숫자·밑줄로 입력합니다.</small>
                  </div>
                  <label className="acs-product-variant-images">Variant 전용 이미지 (최대 12개)
                    <select aria-label="Variant 전용 이미지" multiple size={4} value={variantImageAssetIds} onChange={(event) => setVariantImageAssetIds(Array.from(event.currentTarget.selectedOptions, (option) => option.value))} disabled={busy || images.length === 0}>
                      {images.map((image) => <option key={image.asset_id} value={image.asset_id}>{image.original_filename}</option>)}
                    </select>
                    <small>선택한 전용 이미지가 Lookbook에 우선 사용됩니다. 선택하지 않으면 상품 대표/갤러리 이미지를 사용합니다.</small>
                  </label>
                  <button type="submit" disabled={busy || (!variantColor.trim() && !variantSize.trim() && Object.keys(variantExtraOptions).length === 0) || variantImageAssetIds.length > 12}>{editingVariantId ? 'Variant 변경 저장' : 'Variant 등록'}</button>
                  {editingVariantId && <button type="button" disabled={busy} onClick={clearVariantForm}>편집 취소</button>}
                </form>}
              </div>
            </div>
            <div><button type="button" disabled={busy} onClick={() => startProductEdit(product)}>상품 편집</button><button type="button" disabled={busy} onClick={() => archiveProduct(product.product_id)}>상품 보관</button></div>
          </article>)}
          {products.length === 0 && <p>등록된 상품이 없습니다.</p>}
        </section>
      </div>
    </section>
  );
}

export default ProductCatalogWorkspace;
