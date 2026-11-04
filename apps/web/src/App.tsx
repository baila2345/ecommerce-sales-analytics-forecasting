import { AppRouter } from "./app/router";
import { AuthProvider } from "./features/auth/AuthProvider";

export default function App() {
  return (
    <AuthProvider>
      <AppRouter />
    </AuthProvider>
  );
}
