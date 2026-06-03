import React, { ErrorInfo, ReactNode } from 'react';
import { Bot, RefreshCw } from 'lucide-react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class GlobalErrorBoundary extends React.Component<Props, State> {
  public state: State = {
    hasError: false
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error:', error, errorInfo);
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: undefined });
    window.location.reload();
  };

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      return (
        <div className="min-h-screen bg-[#0a0a1a] flex flex-col items-center justify-center p-6 text-center text-white">
          <div className="bg-red-500/10 border border-red-500/20 p-8 rounded-3xl max-w-md w-full backdrop-blur-md">
            <div className="w-16 h-16 bg-red-500/20 rounded-2xl flex items-center justify-center mx-auto mb-6">
              <Bot className="w-8 h-8 text-red-400" />
            </div>
            <h1 className="text-2xl font-bold mb-2">Simulation Overload</h1>
            <p className="text-gray-400 text-sm mb-6">
              Our sensors encountered an unexpected anomaly. We've logged this failure in the telemetry database.
            </p>
            <div className="bg-black/40 p-4 rounded-xl text-left font-mono text-xs text-red-300 mb-6 overflow-hidden text-ellipsis">
              {this.state.error?.message || 'Unknown Physics Engine Error'}
            </div>
            <button
              onClick={this.handleReset}
              className="w-full py-3 bg-red-500 hover:bg-red-600 text-white rounded-xl font-bold transition-all flex items-center justify-center gap-2"
            >
              <RefreshCw className="w-4 h-4" />
              Reboot System
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
