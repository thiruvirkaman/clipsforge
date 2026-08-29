/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Absolute API origin (e.g. "https://api.example.com"), optional --
   * unset means the API is called via a relative /api/v1 path. */
  readonly VITE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
