import type { ChangeEvent, FormEvent } from "react";

import type {
  AnalyticsFilterOptions,
  AnalyticsFilters as FilterValues,
} from "../types";


type Props = {
  filters: FilterValues;
  options: AnalyticsFilterOptions | null;
  busy: boolean;
  onChange: (filters: FilterValues) => void;
  onApply: () => void;
  onReset: () => void;
  onExport: () => void;
};

export function AnalyticsFilters({
  filters,
  options,
  busy,
  onChange,
  onApply,
  onReset,
  onExport,
}: Props) {
  function change(event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) {
    onChange({ ...filters, [event.target.name]: event.target.value });
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    onApply();
  }

  return (
    <form className="analytics-filter-bar" onSubmit={submit}>
      <label>
        <span>Từ ngày</span>
        <input
          name="date_from"
          type="date"
          min={options?.min_date ?? undefined}
          max={filters.date_to || options?.max_date || undefined}
          value={filters.date_from ?? ""}
          onChange={change}
        />
      </label>
      <label>
        <span>Đến ngày</span>
        <input
          name="date_to"
          type="date"
          min={filters.date_from || options?.min_date || undefined}
          max={options?.max_date ?? undefined}
          value={filters.date_to ?? ""}
          onChange={change}
        />
      </label>
      <label>
        <span>Bang khách hàng</span>
        <select name="state" value={filters.state ?? ""} onChange={change}>
          <option value="">Tất cả bang</option>
          {options?.states.map((state) => <option key={state}>{state}</option>)}
        </select>
      </label>
      <label>
        <span>Danh mục</span>
        <select name="category" value={filters.category ?? ""} onChange={change}>
          <option value="">Tất cả danh mục</option>
          {options?.categories.map((category) => (
            <option key={category} value={category}>{category}</option>
          ))}
        </select>
      </label>
      <label>
        <span>Seller</span>
        <select name="seller_id" value={filters.seller_id ?? ""} onChange={change}>
          <option value="">Tất cả seller</option>
          {options?.sellers.map((seller) => (
            <option key={seller.id} value={seller.id}>{seller.label}</option>
          ))}
        </select>
      </label>
      <div className="analytics-filter-actions">
        <button className="button button--primary filter-submit" type="submit" disabled={busy}>
          {busy ? "Đang tải..." : "Áp dụng"}
        </button>
        <button className="button button--ghost" type="button" onClick={onReset}>Đặt lại</button>
        <button className="button button--ghost export-button" type="button" onClick={onExport} disabled={busy}>
          <span aria-hidden="true">↓</span> Export CSV
        </button>
      </div>
    </form>
  );
}
