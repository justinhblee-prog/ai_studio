export interface ReportGltfParseErrorArgs {
  cancelled: boolean;
  message: string;
  setErrorMessage: (message: string) => void;
  setLoadState: (state: 'error') => void;
  notifyError?: (message: string) => void;
}
export declare function reportGltfParseError(args: ReportGltfParseErrorArgs): boolean;
