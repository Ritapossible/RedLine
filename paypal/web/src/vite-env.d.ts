/// <reference types="vite/client" />
interface ImportMetaEnv {
  /** The RedLine server. Unset: the in-browser preview (simulated PayPal and models). */
  readonly VITE_API_URL?: string;
}
