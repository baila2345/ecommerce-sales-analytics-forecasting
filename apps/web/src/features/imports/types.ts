export type ImportValidationError = {
  row_number: number | null;
  field_name: string | null;
  code: string;
  message: string;
};

export type DatasetInfo = {
  dataset_type: string;
  route_slug: string;
  display_name: string;
  expected_filename: string;
  columns: string[];
  max_file_size_mb: number;
};

export type ImportPreview = {
  batch_id: number;
  dataset_type: string;
  filename: string;
  columns: string[];
  total_rows: number;
  valid_rows: number;
  rejected_rows: number;
  preview_rows: Record<string, unknown>[];
  errors: ImportValidationError[];
  can_import: boolean;
};

export type ImportCommitResult = {
  batch_id: number;
  dataset_type: string;
  status: "completed";
  imported_rows: number;
};
