export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8685/api";

export interface ApiResponse<T> {
  status?: string;
  message?: string;
  data?: T;
  [key: string]: unknown;
}

export interface PricePoint {
  date: string;
  price: number;
}

export interface MarketData {
  data: Record<string, PricePoint[]>;
  tickers: string[];
  date_range: {
    start: string;
    end: string;
  };
}

export interface Strategy {
  strategy_id: string;
  type: string;
  version: string;
  config?: Record<string, unknown>;
  params?: Record<string, unknown>;
}

export interface SelectorConfig {
  class_name: string;
  alias: string;
  activate: boolean;
  params: Record<string, unknown>;
}

export interface RunStrategyParams {
  trade_date: string;
  mode: "universe" | "market";
  selector_names?: string[];
  selector_params?: Record<string, Record<string, unknown>>;
  tickers?: string[];
}

export interface RunStrategyResult {
  status: string;
  count: number;
  data: unknown[];
  saved: boolean;
  message: string;
}

export interface HistoryRecord {
  date: string;
  count: number;
  file: string;
}

export interface ForecastRequest {
  tickers: string[];
  horizon?: number;
  model_type?: string;
  lookback_days?: number;
}

export interface ForecastResult {
  ticker: string;
  predictions: PricePoint[];
  horizon: number;
}

export interface Signal {
  timestamp: string;
  ticker: string;
  model_id: string;
  prediction: number;
  direction: number;
  confidence: number;
  signal: string;
  status: string;
}

export interface SignalStats {
  total: number;
  pending: number;
  executed: number;
  expired: number;
  by_direction: {
    buy: number;
    sell: number;
    hold: number;
  };
}

// --- Paper Trading Interfaces ---

export interface PaperAccountInfo {
    status: string;
    account_id: number;
    account_name: string;
    currency: string;
    portfolio: {
        total_assets: number;
        cash: number;
        market_value: number;
        positions: Position[];
    }
}

export interface Position {
    ticker: string;
    shares: number;
    avg_cost: number;
    updated_at: string;
    current_price?: number;
    market_value?: number;
    unrealized_pnl?: number;
    return_pct?: number;
}

export interface TradeHistoryRecord {
    ticker: string;
    action: string;
    price: number;
    shares: number;
    fee: number;
    trade_time: string;
}

export interface TradeOrderRequest {
    account_id?: number;
    ticker: string;
    action: "BUY" | "SELL";
    shares: number;
    price?: number;
}

export interface CreateAccountRequest {
    name: string;
    initial_balance?: number;
}

// --- Market Scanner Interfaces ---

export interface ScanMarketRequest {
    market: "CN" | "HK";
    strategy_config: {
        name: string;
        params: Record<string, unknown>;
    };
    limit?: number;
}

export interface ScanResultItem {
    ticker: string;
    price: number;
    date: string;
}

export interface ScanResult {
    status: string;
    count: number;
    results: ScanResultItem[];
}

/**
 * 获取认证 Headers（自动注入 Token）
 */
function getAuthHeaders(): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("token");
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
  }
  return headers;
}

export async function fetchApi<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;
  
  const headers = {
    ...getAuthHeaders(),
    ...options.headers,
  };

  const response = await fetch(url, {
    ...options,
    headers,
  });

  // Token 过期或无效 → 自动跳转登录页
  if (response.status === 401) {
    if (typeof window !== "undefined") {
      localStorage.removeItem("token");
      localStorage.removeItem("user");
      window.location.href = "/login";
    }
    throw new Error("认证已过期，请重新登录");
  }

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `API Request failed: ${response.statusText}`);
  }

  return response.json();
}

export interface DataSourceResponse {
  sources: string[];
  api_keys: Record<string, string>;
}

export interface Asset {
  ticker: string;
  name?: string;
  alias?: string;
  last_price?: number;
}

// API Methods
export const api = {
  data: {
    getPrices: (tickers: string[], days: number = 365) => 
      fetchApi<MarketData>(`/data/prices?tickers=${tickers.join(",")}&days=${days}`),
  },
  strategies: {
    list: () => fetchApi<Strategy[]>("/strategies/"),
    get: (id: string) => fetchApi<Strategy>(`/strategies/${id}`),
    generateSignals: (id: string, tickers: string[]) => 
      fetchApi<{ signals: Signal[] }>(`/strategies/${id}/generate-signals`, {
        method: "POST",
        body: JSON.stringify({ tickers }),
      }),
  },
  stz: {
    listStrategies: () => fetchApi<SelectorConfig[]>("/stz/strategies"),
    run: (params: RunStrategyParams) => fetchApi<RunStrategyResult>("/stz/run", {
        method: "POST",
        body: JSON.stringify(params),
    }),
    getAssetPool: () => fetchApi<Asset[]>("/stz/asset-pool"),
    updateAssetPool: (tickers: Asset[]) => fetchApi<{ tickers: Asset[] }>("/stz/asset-pool", {
        method: "POST",
        body: JSON.stringify({ tickers }),
    }),
    addAsset: (ticker: string, alias?: string) => fetchApi<{ status: string; message: string; pool: Asset[] }>("/stz/asset-pool/add", {
        method: "POST",
        body: JSON.stringify({ ticker, alias }),
    }),
    deleteAsset: (ticker: string) => fetchApi<{ status: string; message: string; pool: Asset[] }>("/stz/asset-pool/delete", {
        method: "POST",
        body: JSON.stringify({ ticker }),
    }),
    updateAssetAlias: (ticker: string, alias: string) => fetchApi<{ status: string; message: string; pool: Asset[] }>("/stz/asset-pool/update-alias", {
        method: "POST",
        body: JSON.stringify({ ticker, alias }),
    }),
    getDataSources: () => fetchApi<DataSourceResponse>("/stz/data-sources"),
    updateDataSources: (sources: string[], api_keys?: Record<string, string>) => fetchApi<{ sources: string[] }>("/stz/data-sources", {
        method: "POST",
        body: JSON.stringify({ sources, api_keys }),
    }),
    getHistory: () => fetchApi<HistoryRecord[]>("/stz/history"),
    getHistoryDetail: (date: string) => fetchApi<unknown[]>("/stz/history/" + date),
  },
  forecasting: {
    predict: (data: { tickers: string[], horizon: number, model_type: string }) =>
      fetchApi<any>("/forecasting/predict", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    getPrediction: (ticker: string, horizon: number, model_type: string, lookback_days: number) =>
      fetchApi<ForecastResult>(`/forecasting/predict/${ticker}?horizon=${horizon}&model_type=${model_type}&lookback_days=${lookback_days}`),
  },
  signals: {
    list: (params: { ticker?: string; days?: number; status?: string } = {}) => {
      const query = new URLSearchParams();
      if (params.ticker) query.append("ticker", params.ticker);
      if (params.days) query.append("days", params.days.toString());
      if (params.status) query.append("status", params.status);
      return fetchApi<Signal[]>(`/signals/?${query.toString()}`);
    },
    getStats: (days: number = 7) => 
      fetchApi<SignalStats>(`/signals/stats?days=${days}`),
  },
  trading: {
    execute: (payload: { signals: Signal[]; strategy_id: string; tickers: string[] }) => 
      fetchApi<unknown>("/trading/execute", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    // Paper Trading Endpoints
    paper: {
        createAccount: (data: CreateAccountRequest) =>
            fetchApi("/trading/paper/account", {
                method: "POST",
                body: JSON.stringify(data),
            }),
        getAccount: (accountId?: number) =>
            fetchApi<PaperAccountInfo>(`/trading/paper/account${accountId ? `?account_id=${accountId}` : ''}`, {
                method: "GET",
            }),
        placeOrder: (data: TradeOrderRequest) =>
            fetchApi("/trading/paper/order", {
                method: "POST",
                body: JSON.stringify(data),
            }),
        getHistory: (accountId?: number, limit: number = 50) =>
            fetchApi<TradeHistoryRecord[]>(`/trading/paper/history?limit=${limit}${accountId ? `&account_id=${accountId}` : ''}`, {
                method: "GET",
            }),
        runSettlement: (accountId?: number) =>
            fetchApi<{ status: string; date: string; equity: number; cash: number; position_value: number }>(
                `/trading/paper/settlement${accountId ? `?account_id=${accountId}` : ''}`,
                { method: "POST" }
            ),
        getEquityHistory: (accountId?: number, days: number = 90) =>
            fetchApi<{ equity_history: { date: string; equity: number; cash: number; position_value: number }[] }>(
                `/trading/paper/equity?days=${days}${accountId ? `&account_id=${accountId}` : ''}`
            ),
    }
  },
  scanner: {
      scan: (data: ScanMarketRequest) => 
        fetchApi<ScanResult>("/stz/scan/market", {
            method: "POST",
            body: JSON.stringify(data),
        })
  },
  accounts: {
    getPaperAccount: () => fetchApi<any>("/accounts/paper"),
    getEquityHistory: () => fetchApi<{ equity_history: { date: string; equity: number }[] }>("/accounts/paper/equity"),
    getPositions: () => fetchApi<{ positions: Record<string, number> }>("/accounts/paper/positions"),
    getTrades: (limit?: number) => fetchApi<{ trades: any[]; count: number }>(`/accounts/paper/trades${limit ? `?limit=${limit}` : ""}`),
  },
  backtest: {
    listStrategies: () => fetchApi<any[]>("/backtest/strategies"),
    run: (data: any) => fetchApi<any>("/backtest/run", {
        method: "POST",
        body: JSON.stringify(data),
    }),
  }
};
