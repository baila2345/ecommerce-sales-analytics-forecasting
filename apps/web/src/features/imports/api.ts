import { apiRequest } from "../../api/client";
import { tokenStorage } from "../auth/storage";
import type { DatasetInfo, ImportCommitResult, ImportPreview } from "./types";


function fileForm(file: File): FormData {
  const form = new FormData();
  form.append("file", file);
  return form;
}

export function listImportDatasets(): Promise<DatasetInfo[]> {
  return apiRequest<DatasetInfo[]>("/api/v1/imports/datasets", {
    token: tokenStorage.get(),
  });
}

export function previewDataset(
  routeSlug: string,
  file: File,
): Promise<ImportPreview> {
  return apiRequest<ImportPreview>(
    `/api/v1/imports/${routeSlug}/preview`,
    {
      method: "POST",
      body: fileForm(file),
      token: tokenStorage.get(),
    },
  );
}

export function commitDataset(
  routeSlug: string,
  batchId: number,
  file: File,
): Promise<ImportCommitResult> {
  return apiRequest<ImportCommitResult>(
    `/api/v1/imports/${routeSlug}/${batchId}/commit`,
    {
      method: "POST",
      body: fileForm(file),
      token: tokenStorage.get(),
    },
  );
}
