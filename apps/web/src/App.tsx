import { useEffect, useState } from "react";

type ApiState = "checking" | "online" | "offline";

const apiUrl = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export default function App() {
  const [apiState, setApiState] = useState<ApiState>("checking");

  useEffect(() => {
    const controller = new AbortController();

    fetch(`${apiUrl}/health`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Health check failed with ${response.status}`);
        }
        setApiState("online");
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }
        setApiState("offline");
      });

    return () => controller.abort();
  }, []);

  return (
    <main className="shell">
      <section className="panel">
        <p className="eyebrow">Docker Foundation</p>
        <h1>E-commerce Sales Analytics</h1>
        <p className="description">
          Nền tảng phân tích dữ liệu bán hàng và dự báo doanh thu thương mại điện tử.
        </p>
        <div className={`status status--${apiState}`}>
          <span className="status__dot" aria-hidden="true" />
          API: {apiState === "checking" ? "đang kiểm tra" : apiState === "online" ? "đã kết nối" : "mất kết nối"}
        </div>
      </section>
    </main>
  );
}
