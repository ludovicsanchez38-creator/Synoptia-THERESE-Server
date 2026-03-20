import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center px-4" style={{ backgroundColor: "var(--color-bg)" }}>
          <div className="text-center max-w-md">
            <h1 className="text-2xl font-bold text-red-400 mb-4">Une erreur est survenue</h1>
            <p className="text-[var(--color-muted)] mb-6">
              L'application a rencontré un problème. Veuillez rafraîchir la page.
            </p>
            <button
              onClick={() => window.location.reload()}
              className="px-6 py-2 bg-[var(--color-primary)] text-white rounded-lg hover:opacity-90"
            >
              Rafraîchir la page
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
