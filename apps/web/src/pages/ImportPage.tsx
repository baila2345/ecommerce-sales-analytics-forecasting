import {
  type ChangeEvent,
  type FormEvent,
  useEffect,
  useMemo,
  useState,
} from "react";

import { ApiError } from "../api/client";
import { useAuth } from "../features/auth/AuthProvider";
import {
  commitDataset,
  listImportDatasets,
  previewDataset,
} from "../features/imports/api";
import type {
  DatasetInfo,
  ImportCommitResult,
  ImportPreview,
} from "../features/imports/types";


type RequestState = "idle" | "previewing" | "ready" | "importing" | "done";

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  return String(value);
}

export function ImportPage() {
  const { user } = useAuth();
  const [datasets, setDatasets] = useState<DatasetInfo[]>([]);
  const [selectedSlug, setSelectedSlug] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [result, setResult] = useState<ImportCommitResult | null>(null);
  const [requestState, setRequestState] = useState<RequestState>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const canManageImports = user?.role === "admin" || user?.role === "analyst";
  const selectedDataset = useMemo(
    () => datasets.find((dataset) => dataset.route_slug === selectedSlug) ?? null,
    [datasets, selectedSlug],
  );

  useEffect(() => {
    if (!canManageImports) return;
    let active = true;
    listImportDatasets()
      .then((response) => {
        if (!active) return;
        setDatasets(response);
        setSelectedSlug(response[0]?.route_slug ?? "");
      })
      .catch((error) => {
        if (!active) return;
        setErrorMessage(
          error instanceof ApiError
            ? error.message
            : "Không thể tải danh sách loại dữ liệu.",
        );
      });
    return () => {
      active = false;
    };
  }, [canManageImports]);

  function resetSelection() {
    setFile(null);
    setPreview(null);
    setResult(null);
    setErrorMessage(null);
    setRequestState("idle");
  }

  function selectDataset(event: ChangeEvent<HTMLSelectElement>) {
    setSelectedSlug(event.target.value);
    resetSelection();
  }

  function selectFile(event: ChangeEvent<HTMLInputElement>) {
    setFile(event.target.files?.[0] ?? null);
    setPreview(null);
    setResult(null);
    setErrorMessage(null);
    setRequestState("idle");
  }

  async function previewFile(event: FormEvent) {
    event.preventDefault();
    if (!file || !selectedDataset) return;
    setRequestState("previewing");
    setErrorMessage(null);
    try {
      setPreview(await previewDataset(selectedDataset.route_slug, file));
      setRequestState("ready");
    } catch (error) {
      setRequestState("idle");
      setErrorMessage(
        error instanceof ApiError
          ? error.message
          : "Không thể đọc file CSV. Vui lòng thử lại.",
      );
    }
  }

  async function confirmImport() {
    if (!file || !preview?.can_import || !selectedDataset) return;
    setRequestState("importing");
    setErrorMessage(null);
    try {
      setResult(
        await commitDataset(
          selectedDataset.route_slug,
          preview.batch_id,
          file,
        ),
      );
      setRequestState("done");
    } catch (error) {
      setRequestState("ready");
      setErrorMessage(
        error instanceof ApiError
          ? error.message
          : "Không thể import dữ liệu. Vui lòng thử lại.",
      );
    }
  }

  if (!canManageImports) {
    return (
      <main className="import-page">
        <section className="permission-card">
          <span aria-hidden="true">!</span>
          <h1>Bạn không có quyền nhập dữ liệu</h1>
          <p>Chức năng này dành cho quản trị viên và chuyên viên phân tích.</p>
        </section>
      </main>
    );
  }

  return (
    <main className="import-page">
      <header className="page-heading">
        <div>
          <p className="section-label">Data Import</p>
          <h1>Nhập dữ liệu Olist</h1>
          <p>Kiểm tra cấu trúc và xem trước dữ liệu trước khi ghi vào hệ thống.</p>
        </div>
        <span className="step-badge">{datasets.length || 9} loại dữ liệu</span>
      </header>

      <section className="import-card">
        <div className="dataset-selector">
          <label htmlFor="dataset-type">Loại dữ liệu</label>
          <select
            id="dataset-type"
            value={selectedSlug}
            onChange={selectDataset}
            disabled={!datasets.length}
          >
            {datasets.map((dataset) => (
              <option key={dataset.dataset_type} value={dataset.route_slug}>
                {dataset.display_name}
              </option>
            ))}
          </select>
        </div>

        {selectedDataset && (
          <>
            <div className="import-card__heading">
              <div className="dataset-icon">CSV</div>
              <div>
                <h2>{selectedDataset.display_name}</h2>
                <p>File yêu cầu: {selectedDataset.expected_filename}</p>
              </div>
              <span className="dataset-status">Sẵn sàng</span>
            </div>

            <form className="upload-form" onSubmit={previewFile}>
              <label className="file-drop" htmlFor="dataset-csv">
                <span className="file-drop__icon" aria-hidden="true">⇧</span>
                <strong>{file ? file.name : "Chọn file CSV"}</strong>
                <small>
                  {file
                    ? `${(file.size / 1024).toFixed(1)} KB`
                    : `UTF-8 · Tối đa ${selectedDataset.max_file_size_mb} MB`}
                </small>
                <input
                  id="dataset-csv"
                  type="file"
                  accept=".csv,text/csv"
                  onChange={selectFile}
                />
              </label>
              <div className="expected-columns">
                <span>Các cột theo đúng thứ tự</span>
                {selectedDataset.columns.map((column) => (
                  <code key={column}>{column}</code>
                ))}
              </div>
              <button
                className="button button--primary button--preview"
                type="submit"
                disabled={
                  !file ||
                  requestState === "previewing" ||
                  requestState === "importing"
                }
              >
                {requestState === "previewing"
                  ? "Đang kiểm tra..."
                  : "Kiểm tra & xem trước"}
              </button>
            </form>
          </>
        )}
      </section>

      {errorMessage && <div className="form-error" role="alert">{errorMessage}</div>}

      {preview && (
        <section className="preview-card" aria-live="polite">
          <div className="preview-summary">
            <div><span>Tổng số dòng</span><strong>{preview.total_rows}</strong></div>
            <div><span>Hợp lệ</span><strong className="text-success">{preview.valid_rows}</strong></div>
            <div><span>Bị từ chối</span><strong className={preview.rejected_rows ? "text-danger" : ""}>{preview.rejected_rows}</strong></div>
            <div><span>Trạng thái</span><strong>{preview.can_import ? "Có thể import" : "Cần sửa file"}</strong></div>
          </div>

          {preview.preview_rows.length > 0 && (
            <div className="table-wrap">
              <div className="table-heading">
                <div><h2>Xem trước dữ liệu</h2><p>Tối đa 5 dòng hợp lệ đầu tiên</p></div>
                <span>{preview.filename}</span>
              </div>
              <table>
                <thead>
                  <tr><th>#</th>{preview.columns.map((column) => <th key={column}>{column}</th>)}</tr>
                </thead>
                <tbody>
                  {preview.preview_rows.map((row, index) => (
                    <tr key={index}>
                      <td>{index + 1}</td>
                      {preview.columns.map((column) => (
                        <td key={column}>{displayValue(row[column])}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {preview.errors.length > 0 && (
            <div className="validation-errors" role="alert">
              <h2>Lỗi dữ liệu</h2>
              <ul>
                {preview.errors.map((error, index) => (
                  <li key={`${error.row_number}-${error.field_name}-${index}`}>
                    <strong>{error.row_number ? `Dòng ${error.row_number}` : "Cấu trúc file"}</strong>
                    <span>{error.message}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="confirm-row">
            <div>
              <strong>{preview.can_import ? "Dữ liệu đã qua kiểm tra" : "Chưa thể import"}</strong>
              <p>{preview.can_import ? "Xác nhận để ghi dữ liệu vào database." : "Sửa các lỗi trên rồi chọn lại file."}</p>
            </div>
            <button
              className="button button--primary button--confirm"
              type="button"
              disabled={
                !preview.can_import ||
                requestState === "importing" ||
                requestState === "done"
              }
              onClick={confirmImport}
            >
              {requestState === "importing"
                ? "Đang import..."
                : requestState === "done"
                  ? "Đã import"
                  : "Xác nhận import"}
            </button>
          </div>
        </section>
      )}

      {result && (
        <div className="import-success" role="status">
          <span aria-hidden="true">✓</span>
          <div>
            <strong>Import thành công</strong>
            <p>Đã ghi {result.imported_rows} dòng vào database.</p>
          </div>
        </div>
      )}
    </main>
  );
}
