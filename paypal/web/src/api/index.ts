import { HttpApi } from "./http";
import { PreviewApi } from "./mock/engine";
import type { RedLineApi } from "./types";

/** The server when VITE_API_URL is set; otherwise the in-browser preview. */
export const api: RedLineApi = import.meta.env.VITE_API_URL ? new HttpApi(import.meta.env.VITE_API_URL) : new PreviewApi();
export const PREVIEW = !import.meta.env.VITE_API_URL;
export { ApiError } from "./errors";
export type * from "./types";
