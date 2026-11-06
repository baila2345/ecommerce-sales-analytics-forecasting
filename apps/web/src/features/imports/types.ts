export type ProductCategoryPreviewRow = {
  product_category_name: string;
  product_category_name_english: string;
};

export type ImportValidationError = {
  row_number: number | null;
  field_name: string | null;
  code: string;
  message: string;
};

export type ProductCategoryPreview = {
  batch_id: number;
  dataset_type: "product_categories";
  filename: string;
  columns: string[];
  total_rows: number;
  valid_rows: number;
  rejected_rows: number;
  preview_rows: ProductCategoryPreviewRow[];
  errors: ImportValidationError[];
  can_import: boolean;
};

export type ImportCommitResult = {
  batch_id: number;
  dataset_type: "product_categories";
  status: "completed";
  imported_rows: number;
};
