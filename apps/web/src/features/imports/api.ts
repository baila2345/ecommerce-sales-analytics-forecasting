import { apiRequest } from "../../api/client";
import { tokenStorage } from "../auth/storage";
import type { ImportCommitResult, ProductCategoryPreview } from "./types";


function fileForm(file: File): FormData {
  const form = new FormData();
  form.append("file", file);
  return form;
}

export function previewProductCategories(
  file: File,
): Promise<ProductCategoryPreview> {
  return apiRequest<ProductCategoryPreview>(
    "/api/v1/imports/product-categories/preview",
    {
      method: "POST",
      body: fileForm(file),
      token: tokenStorage.get(),
    },
  );
}

export function commitProductCategories(
  batchId: number,
  file: File,
): Promise<ImportCommitResult> {
  return apiRequest<ImportCommitResult>(
    `/api/v1/imports/product-categories/${batchId}/commit`,
    {
      method: "POST",
      body: fileForm(file),
      token: tokenStorage.get(),
    },
  );
}
