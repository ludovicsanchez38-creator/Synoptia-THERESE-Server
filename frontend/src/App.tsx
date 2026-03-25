import { lazy, Suspense, useCallback, useEffect, useState } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { useAuthStore } from "./stores/authStore";
import CharterModal from "./components/CharterModal";
import SearchModal from "./components/SearchModal";
import Spinner from "./components/ui/Spinner";

// Lazy-loaded pages (code splitting)
const LoginPage = lazy(() => import("./pages/Login"));
const ChatPage = lazy(() => import("./pages/Chat"));
const TasksPage = lazy(() => import("./pages/Tasks"));
const CRMPage = lazy(() => import("./pages/CRM"));
const AdminDashboard = lazy(() => import("./pages/admin/Dashboard"));
const LegalPage = lazy(() => import("./pages/Legal"));

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { user } = useAuthStore();
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function AdminRoute({ children }: { children: React.ReactNode }) {
  const { user } = useAuthStore();
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== "admin") return <Navigate to="/chat" replace />;
  return <>{children}</>;
}

export default function App() {
  const { user, isLoading, checkAuth } = useAuthStore();
  const [searchOpen, setSearchOpen] = useState(false);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  // Ctrl+K / Cmd+K pour ouvrir la recherche
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        if (user) setSearchOpen((open) => !open);
      }
    },
    [user]
  );

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <Spinner size="lg" />
          <p className="mt-4 text-sm text-[var(--color-muted)]">
            Chargement...
          </p>
        </div>
      </div>
    );
  }

  // Charte IA obligatoire avant toute utilisation
  if (user && !user.charter_accepted) {
    return <CharterModal />;
  }

  return (
    <>
    {searchOpen && <SearchModal onClose={() => setSearchOpen(false)} />}
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center"><div className="text-center"><Spinner size="lg" /><p className="mt-4 text-sm text-[var(--color-muted)]">Chargement...</p></div></div>}>
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/chat"
        element={
          <PrivateRoute>
            <ChatPage />
          </PrivateRoute>
        }
      />
      <Route
        path="/tasks"
        element={
          <PrivateRoute>
            <TasksPage />
          </PrivateRoute>
        }
      />
      <Route
        path="/crm"
        element={
          <PrivateRoute>
            <CRMPage />
          </PrivateRoute>
        }
      />
      <Route
        path="/admin/*"
        element={
          <AdminRoute>
            <AdminDashboard />
          </AdminRoute>
        }
      />
      <Route path="/legal" element={<LegalPage />} />
      <Route path="*" element={<Navigate to="/chat" replace />} />
    </Routes>
    </Suspense>
    </>
  );
}
