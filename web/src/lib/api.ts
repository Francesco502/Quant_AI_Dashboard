export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8685/api"

function normalizeBaseUrl(base: string): string {
  // Remove trailing slashes to avoid `.../api//path`.
  return base.replace(/\/+$/, "")
}

function isLoopbackHost(host: string): boolean {
  return host === "localhost" || host === "127.0.0.1"
}

function harmonizeLocalDevBaseUrl(base: string): string {
  if (typeof window === "undefined") return base

  try {
    const parsed = new URL(base)
    const currentHost = window.location.hostname
    if (isLoopbackHost(parsed.hostname) && isLoopbackHost(currentHost) && parsed.hostname !== currentHost) {
      parsed.hostname = currentHost
      return normalizeBaseUrl(parsed.toString())
    }
  } catch {
    return base
  }

  return base
}

function normalizeEndpoint(endpoint: string): string {
  if (!endpoint) return "/"
  return endpoint.startsWith("/") ? endpoint : `/${endpoint}`
}

/**
 * 配置驱动的 API 基址解析（唯一权威）。
 *
 * - `NEXT_PUBLIC_API_URL` 为绝对 URL：原样使用（例如本地 `http://127.0.0.1:8685/api`）
 * - `NEXT_PUBLIC_API_URL` 为相对路径（以 `/` 开头）：浏览器端拼接到同源（例如线上 `/api`）
 *
 * 注意：当前项目约束为“仅在客户端调用 API”；如需 SSR 调用，需引入 `SITE_ORIGIN` 并扩展该函数。
 */
export function resolveApiBaseUrl(): string {
  const configured = API_BASE_URL
  if (typeof window === "undefined") {
    return normalizeBaseUrl(configured)
  }
  const normalized = configured.trim()
  if (normalized.startsWith("/")) {
    return normalizeBaseUrl(`${window.location.origin}${normalized}`)
  }
  return harmonizeLocalDevBaseUrl(normalizeBaseUrl(normalized))
}

// Backward compatible export (avoid touching too many call sites).
export const getEffectiveApiBaseUrl = resolveApiBaseUrl

export interface ApiResponse<T> {
  status?: string;
  message?: string;
  data?: T;
  [key: string]: unknown;
}

export type UnknownRecord = Record<string, unknown>;
export type UnknownArray = unknown[];

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
  market?: "CN" | "HK";
  min_score?: number;
  top_n?: number;
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
  metrics?: {
    MAE?: number;
    RMSE?: number;
    MAPE?: number;
    mae?: number;
    rmse?: number;
    mape?: number;
    [key: string]: number | undefined;
  };
}

// --- Strategy Template Interfaces ---

export interface StrategyTemplate {
  id: number;
  template_name: string;
  strategy_id: string;
  strategy_type: string;
  description?: string;
  params: Record<string, unknown>;
  is_public: boolean;
  is_favorite: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateTemplateRequest {
  template_name: string;
  strategy_id: string;
  strategy_type: string;
  description?: string;
  params: Record<string, unknown>;
  is_public?: boolean;
}

export interface UpdateTemplateRequest {
  template_name?: string;
  description?: string;
  params?: Record<string, unknown>;
  is_public?: boolean;
  is_favorite?: boolean;
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

interface PaperPositionBackend {
    shares?: number;
    avg_cost?: number;
    market_value?: number;
    unrealized_pnl?: number;
}

interface PaperAccountBackendResponse {
    account_id?: number | null;
    account_name?: string | null;
    balance?: number;
    frozen?: number;
    total_assets?: number;
    positions?: Record<string, PaperPositionBackend>;
    portfolio?: {
        total_assets?: number;
        cash?: number;
        market_value?: number;
        position_value?: number;
    };
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
    order_type?: "MARKET" | "LIMIT" | "STOP" | "STOP_LIMIT";
    price?: number;
    stop_price?: number;
}

export interface CreateAccountRequest {
    name: string;
    initial_balance?: number;
}

export interface PerformanceMetrics {
    account_id: number;
    initial_capital: number;
    total_assets: number;
    cash: number;
    market_value: number;
    total_return_pct: number;
    annual_return_pct: number;
    sharpe_ratio: number;
    max_drawdown_pct: number;
    win_rate_pct: number;
    total_trades: number;
    profitable_trades: number;
    days_active: number;
    timestamp: string;
}

export interface EquityPoint {
    date: string;
    equity: number;
    cash: number;
    market_value: number;
}

export interface EquityCurve {
    account_id: number;
    days: number;
    data: EquityPoint[];
    count: number;
}

export interface AutoTradingConfig {
    enabled: boolean;
    interval_minutes: number;
    username: string;
    account_name: string;
    initial_capital: number;
    strategy_ids: string[];
    universe_mode: "manual" | "asset_pool" | "cn_a_share";
    universe: string[];
    universe_limit: number;
    max_positions: number;
    evaluation_days: number;
    min_total_return: number;
    min_sharpe_ratio: number;
    max_drawdown: number;
    top_n_strategies: number;
}

export interface AutoTradingStrategySummary {
    id: string;
    name: string;
    description: string;
    category?: string;
    default_params?: Record<string, unknown>;
}

export interface AutoTradingDaemonStatus {
    daemon_running?: boolean;
    daemon_pid?: number;
    last_started_at?: string;
    last_stopped_at?: string;
    last_trading_run?: string;
    last_trading_requested_at?: string;
    last_trading_result?: UnknownRecord;
    last_trading_error?: string | null;
    trading_run_state?: "idle" | "running" | "failed" | string;
    config_trading_enabled?: boolean;
    config_trading_interval_minutes?: number;
}

export interface AutoTradingAccountSnapshot {
    found: boolean;
    username: string;
    user_id?: number;
    account_id?: number;
    account_name: string;
    balance?: number;
    initial_capital?: number;
    portfolio?: {
        total_assets: number;
        cash: number;
        market_value: number;
        positions: Position[];
    };
    positions?: Position[];
    recent_trades?: TradeHistoryRecord[];
    recent_orders?: UnknownRecord[];
}

export interface AutoTradingStatusResponse {
    config: AutoTradingConfig;
    daemon: AutoTradingDaemonStatus;
    available_strategies: AutoTradingStrategySummary[];
    account: AutoTradingAccountSnapshot | null;
    run_request_status?: "started" | "already_running" | string;
    message?: string;
    universe_summary?: {
      mode: "manual" | "asset_pool" | "cn_a_share" | string;
      label: string;
      ticker_count: number;
      preview: string[];
    };
    run_result?: UnknownRecord;
}

export interface AutoTradingConfigUpdateRequest {
    enabled?: boolean;
    interval_minutes?: number;
    username?: string;
    account_name?: string;
    initial_capital?: number;
    strategy_ids?: string[];
    universe_mode?: "manual" | "asset_pool" | "cn_a_share";
    universe?: string[];
    universe_limit?: number;
    max_positions?: number;
    evaluation_days?: number;
    min_total_return?: number;
    min_sharpe_ratio?: number;
    max_drawdown?: number;
    top_n_strategies?: number;
}

export interface DecisionDashboardResult {
    ticker: string;
    conclusion: string;
    action: string;
    score: number;
    buy_price: number | null;
    stop_loss: number | null;
    target_price: number | null;
    checklist: {
        condition: string;
        status: string;
        value: string;
    }[];
    highlights: string[];
    risks: string[];
    latest_price?: number;
    latest_rsi?: number;
    timestamp: string;
}

export interface ReturnContributionItem {
    ticker: string;
    return_pct: number;
    contribution_pct: number;
    weight: number;
}

export interface PortfolioAnalyzeResponse {
    summary: Record<string, unknown>;
    asset_metrics: Array<Record<string, unknown>>;
    risk_metrics: {
        max_drawdown: number;
        var_95: number;
        cvar_95?: number;
    };
    recommendations: Array<Record<string, unknown>>;
    correlations: number[][];
    contributions: ReturnContributionItem[];
    return_attribution?: Record<string, unknown>;
    risk_contributions?: Array<Record<string, unknown>>;
    factor_exposures?: Array<Record<string, unknown>>;
    benchmark_attribution?: Record<string, unknown>;
    highly_correlated_pairs: Array<Record<string, unknown>>;
    technical_signals: Array<Record<string, unknown>>;
  timestamp: string;
}

export interface AssetTypeResponse extends UnknownRecord {
  ticker: string;
  asset_type?: string;
  market?: string;
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

export interface BacktestStrategyResult extends UnknownRecord {
  metrics?: Record<string, number>;
  equity_curve?: UnknownArray;
  trades?: UnknownArray;
}

export interface BacktestPortfolioResult extends UnknownRecord {
  metrics?: Record<string, number>;
  equity_curve?: UnknownArray;
  trades?: UnknownArray;
  weights?: Record<string, number>;
}

export interface BacktestRunResponse extends UnknownRecord {
  portfolio?: BacktestPortfolioResult;
  individual?: Record<string, BacktestStrategyResult>;
  metrics?: Record<string, number>;
  equity_curve?: UnknownArray;
  trades?: UnknownArray;
  stz_result?: UnknownRecord;
}

export interface BacktestExportResponse extends UnknownRecord {
  download_url?: string;
  format?: string;
}

/**
 * Build auth headers and auto-attach bearer token from localStorage.
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
  const base = resolveApiBaseUrl()
  const url = `${base}${normalizeEndpoint(endpoint)}`
  
  const headers = {
    ...getAuthHeaders(),
    ...options.headers,
  };

  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
    });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      throw error;
    }
    const message =
      error instanceof Error && error.message
        ? error.message
        : "Unknown network error";
    throw new Error(`Cannot reach API service (${url}). ${message}`);
  }

  // Redirect to login when token is missing/expired.
  if (response.status === 401) {
    if (typeof window !== "undefined") {
      localStorage.removeItem("token");
      localStorage.removeItem("user");
      window.location.href = "/login";
    }
    throw new Error("Authentication expired. Please sign in again.");
  }
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `API Request failed: ${response.statusText}`);
  }

  return response.json();
}

function toNumber(value: unknown, fallback = 0): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
  }
  return fallback;
}

function normalizePaperAccount(payload: PaperAccountBackendResponse): PaperAccountInfo | null {
  const accountId = payload?.account_id;
  if (accountId === null || accountId === undefined) {
    return null;
  }

  const accountPortfolio = payload?.portfolio;
  const cash = toNumber(payload?.balance ?? accountPortfolio?.cash, 0);
  const totalAssets = toNumber(payload?.total_assets ?? accountPortfolio?.total_assets, 0);

  const positionsObj = payload?.positions ?? {};
  const positions = Object.entries(positionsObj).map(([ticker, pos]) => ({
    ticker,
    shares: toNumber(pos?.shares, 0),
    avg_cost: toNumber(pos?.avg_cost, 0),
    updated_at: "",
    market_value: toNumber(pos?.market_value, 0),
    unrealized_pnl: toNumber(pos?.unrealized_pnl, 0),
  }));

  const summedMarketValue = positions.reduce((sum, p) => sum + toNumber(p.market_value, 0), 0);
  const fallbackMarketValue = Math.max(totalAssets - cash, 0);
  const marketValue = toNumber(
    accountPortfolio?.market_value ?? accountPortfolio?.position_value,
    summedMarketValue > 0 ? summedMarketValue : fallbackMarketValue
  );

  return {
    status: "success",
    account_id: toNumber(accountId, 0),
    account_name: payload?.account_name || "模拟账户",
    currency: "CNY",
    portfolio: {
      total_assets: totalAssets,
      cash,
      market_value: marketValue,
      positions,
    },
  };
}

export interface DataSourceResponse {
  sources: string[];
  api_key_status: {
    Tushare: boolean;
    AlphaVantage: boolean;
  };
  configuration_mode: "env_locked";
}

export type LlmInterfaceType = "openai_compat" | "anthropic";

export interface LlmRuntimeOptions {
  provider_type?: LlmInterfaceType;
  base_url?: string;
  model?: string;
}

export interface Asset {
  ticker: string;
  name?: string;
  alias?: string;
  last_price?: number;
  asset_type?: string | null;
  last_price_date?: string | null;
  price_source?: string | null;
}

export interface AssetSearchResult {
  ticker: string;
  name: string;
  asset_type: string;
  market?: string;
  source?: string;
  category?: string | null;
  score?: number;
}

export interface UserAssetDcaRule {
  enabled: boolean;
  frequency: "weekly" | "monthly";
  weekday?: number | null;
  monthday?: number | null;
  amount: number;
  start_date?: string | null;
  end_date?: string | null;
  shift_to_next_trading_day?: boolean;
  last_run_date?: string | null;
}

export interface UserAssetRow {
  ticker: string;
  asset_name?: string | null;
  asset_category?: string | null;
  asset_style?: string | null;
  asset_type?: string | null;
  notes?: string | null;
  units: number;
  avg_cost: number;
  invested_amount: number;
  current_price: number;
  last_price_date?: string | null;
  market_value: number;
  total_return: number;
  total_return_pct: number;
  day_change: number;
  week_change: number;
  month_change: number;
  year_change: number;
  day_change_pct?: number;
  week_change_pct?: number;
  month_change_pct?: number;
  year_change_pct?: number;
  dca_rule?: UserAssetDcaRule | null;
  updated_at?: string | null;
}

export interface UserAssetSummary {
  asset_count: number;
  total_market_value: number;
  total_invested_amount: number;
  total_return: number;
  total_return_pct: number;
  day_change: number;
  week_change: number;
  month_change: number;
  year_change: number;
  updated_at?: string;
}

export interface UserAssetOverview {
  summary: UserAssetSummary;
  assets: UserAssetRow[];
}

export interface UserAssetTransaction {
  id: number;
  ticker: string;
  transaction_type: string;
  trade_date: string;
  quantity: number;
  price: number;
  amount?: number | null;
  fee?: number;
  source?: string;
  note?: string | null;
  created_at?: string;
}

export interface UserAssetUpsertRequest {
  ticker: string;
  asset_name?: string;
  asset_category?: string;
  asset_style?: string;
  asset_type?: string;
  units: number;
  avg_cost: number;
  trade_date?: string;
  notes?: string;
  dca_rule?: UserAssetDcaRule | null;
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
    getAssetPool: (forceRefresh: boolean = false) =>
      fetchApi<Asset[]>(`/stz/asset-pool${forceRefresh ? "?force_refresh=true" : ""}`),
    searchAssets: (query: string, limit: number = 12, options: RequestInit = {}) =>
      fetchApi<AssetSearchResult[]>(`/stz/asset-search?q=${encodeURIComponent(query)}&limit=${limit}`, options),
    updateAssetPool: (tickers: Asset[]) => fetchApi<{ tickers: Asset[] }>("/stz/asset-pool", {
        method: "POST",
        body: JSON.stringify({ tickers }),
    }),
    addAsset: (data: { ticker: string; asset_name?: string; asset_type?: string; alias?: string }) => fetchApi<{ status: string; message: string; pool: Asset[] }>("/stz/asset-pool/add", {
        method: "POST",
        body: JSON.stringify(data),
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
    getHistory: () => fetchApi<HistoryRecord[]>("/stz/history"),
    getHistoryDetail: (date: string) => fetchApi<unknown[]>("/stz/history/" + date),
  },
  forecasting: {
    predict: (data: { tickers: string[], horizon: number, model_type?: string }) =>
      fetchApi<UnknownRecord>("/forecasting/predict", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    getPrediction: (ticker: string, horizon: number, model_type: string, lookback_days: number) =>
      fetchApi<ForecastResult>(`/forecasting/predict/${ticker}?horizon=${horizon}&model_type=${model_type}&lookback_days=${lookback_days}`),
    getModelList: () => fetchApi<{ models: string[] }>("/forecasting/models"),
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
    auto: {
        getStatus: () => fetchApi<AutoTradingStatusResponse>("/trading/auto/status"),
        updateConfig: (data: AutoTradingConfigUpdateRequest) =>
            fetchApi<AutoTradingStatusResponse>("/trading/auto/config", {
                method: "PUT",
                body: JSON.stringify(data),
            }),
        runNow: (data: { reset_account?: boolean; initial_balance?: number } = {}) =>
            fetchApi<AutoTradingStatusResponse>("/trading/auto/run-now", {
                method: "POST",
                body: JSON.stringify(data),
            }),
    },
    // Paper Trading Endpoints
    paper: {
        createAccount: (data: CreateAccountRequest) =>
            fetchApi("/trading/accounts", {
                method: "POST",
                body: JSON.stringify({
                    name: data.name,
                    initial_balance: data.initial_balance ?? 100000,
                }),
            }),
        getAccount: async (accountId?: number): Promise<PaperAccountInfo | null> => {
            if (accountId) {
                const detail = await fetchApi<{
                    account_id?: number;
                    account_name?: string;
                    portfolio?: {
                        total_assets?: number;
                        cash?: number;
                        market_value?: number;
                        position_value?: number;
                    };
                    positions?: Array<{
                        ticker?: string;
                        shares?: number;
                        avg_cost?: number;
                        market_value?: number;
                        unrealized_pnl?: number;
                    }>;
                }>(`/trading/accounts/${accountId}`);

                const positions = Array.isArray(detail.positions)
                    ? detail.positions
                          .filter((item): item is NonNullable<typeof item> => !!item)
                          .map((item) => ({
                              ticker: item.ticker || "",
                              shares: toNumber(item.shares, 0),
                              avg_cost: toNumber(item.avg_cost, 0),
                              updated_at: "",
                              market_value: toNumber(item.market_value, 0),
                              unrealized_pnl: toNumber(item.unrealized_pnl, 0),
                          }))
                    : [];

                return {
                    status: "success",
                    account_id: toNumber(detail.account_id, accountId),
                    account_name: detail.account_name || "模拟账户",
                    currency: "CNY",
                    portfolio: {
                        total_assets: toNumber(detail.portfolio?.total_assets, 0),
                        cash: toNumber(detail.portfolio?.cash, 0),
                        market_value: toNumber(
                            detail.portfolio?.market_value ?? detail.portfolio?.position_value,
                            0
                        ),
                        positions,
                    },
                };
            }

            const payload = await fetchApi<PaperAccountBackendResponse>("/accounts/paper");
            return normalizePaperAccount(payload);
        },
        placeOrder: async (data: TradeOrderRequest) => {
            let accountId = data.account_id;
            if (!accountId) {
                const account = await fetchApi<PaperAccountBackendResponse>("/accounts/paper");
                const normalized = normalizePaperAccount(account);
                if (!normalized?.account_id) {
                    throw new Error("当前没有可用的模拟账户。");
                }
                accountId = normalized.account_id;
            }

            return fetchApi("/trading/orders", {
                method: "POST",
                body: JSON.stringify({
                    account_id: accountId,
                    symbol: data.ticker,
                    side: data.action,
                    order_type: data.order_type || "MARKET",
                    quantity: data.shares,
                    price: data.price,
                    stop_price: data.stop_price,
                }),
            });
        },
        resetAccount: (accountId: number, data: { initial_balance: number; account_name?: string }) =>
            fetchApi<{
                success: boolean;
                account_id: number;
                account_name: string;
                balance: number;
                initial_capital: number;
                message: string;
            }>(`/trading/accounts/${accountId}/reset`, {
                method: "POST",
                body: JSON.stringify(data),
            }),
        getHistory: async (_accountId?: number, limit: number = 50) => {
            const result = await fetchApi<{ trades: TradeHistoryRecord[]; count: number }>(
                `/accounts/paper/trades?limit=${limit}`
            );
            return result.trades ?? [];
        },
        runSettlement: async (accountId?: number) => {
            const account = await api.trading.paper.getAccount(accountId);
            return {
                status: "success",
                message: "模拟账户会按需更新，无需单独执行结算接口。",
                account,
            };
        },
        getEquityHistory: (_accountId?: number, days: number = 90) =>
            fetchApi<{ equity_history: { date: string; equity: number; cash: number; position_value: number }[] }>(
                `/accounts/paper/equity?days=${days}`
            ),
        // New endpoints for performance metrics and equity curve
        getPerformance: (accountId: number) =>
            fetchApi<PerformanceMetrics>(`/trading/accounts/${accountId}/performance`),
        getEquityCurve: (accountId: number, days: number = 30) =>
            fetchApi<EquityCurve>(`/trading/accounts/${accountId}/equity-curve?days=${days}`),
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
    getPaperAccount: () => fetchApi<UnknownRecord>("/accounts/paper"),
    getEquityHistory: () => fetchApi<{ equity_history: { date: string; equity: number }[] }>("/accounts/paper/equity"),
    getPositions: () => fetchApi<{ positions: Record<string, number> }>("/accounts/paper/positions"),
    getTrades: (limit?: number) => fetchApi<{ trades: TradeHistoryRecord[]; count: number }>(`/accounts/paper/trades${limit ? `?limit=${limit}` : ""}`),
  },
  backtest: {
    listStrategies: () => fetchApi<UnknownRecord[]>("/backtest/strategies"),
    run: (data: UnknownRecord) => fetchApi<BacktestRunResponse>("/backtest/run", {
        method: "POST",
        body: JSON.stringify(data),
    }),
    runMulti: (data: UnknownRecord) => fetchApi<BacktestRunResponse>("/backtest/run-multi", {
        method: "POST",
        body: JSON.stringify(data),
    }),
    optimize: (data: UnknownRecord) => fetchApi<OptimizationResult>("/backtest/optimize", {
        method: "POST",
        body: JSON.stringify(data),
    }),
    extendedAnalysis: (data: UnknownRecord) => fetchApi<BacktestExtendedAnalysis>("/backtest/extended-analysis", {
        method: "POST",
        body: JSON.stringify(data),
    }),
    export: (data: UnknownRecord) => fetchApi<BacktestExportResponse>("/backtest/export", {
        method: "POST",
        body: JSON.stringify(data),
    }),
    listBenchmarks: () => fetchApi<{ benchmarks: UnknownRecord[] }>("/backtest/benchmarks"),
    compareStrategies: (data: UnknownRecord) => fetchApi<ComparativeAnalysis>("/backtest/compare-strategies", {
        method: "POST",
        body: JSON.stringify(data),
    }),
    // Strategy Templates
    templates: {
      list: (params?: { strategy_type?: string; is_favorite?: boolean }) => {
        const query = new URLSearchParams()
        if (params?.strategy_type) query.append("strategy_type", params.strategy_type)
        if (params?.is_favorite !== undefined) query.append("is_favorite", String(params.is_favorite))
        return fetchApi<StrategyTemplate[]>(`/strategy-templates?${query.toString()}`)
      },
      get: (id: number) => fetchApi<StrategyTemplate>(`/strategy-templates/${id}`),
      create: (data: CreateTemplateRequest) => fetchApi<StrategyTemplate>("/strategy-templates", {
        method: "POST",
        body: JSON.stringify(data),
      }),
      update: (id: number, data: UpdateTemplateRequest) => fetchApi<StrategyTemplate>(`/strategy-templates/${id}`, {
        method: "PUT",
        body: JSON.stringify(data),
      }),
      delete: (id: number) => fetchApi<UnknownRecord>(`/strategy-templates/${id}`, {
        method: "DELETE",
      }),
      getBacktestHistory: (id: number, limit: number = 10) =>
        fetchApi<UnknownRecord[]>(`/strategy-templates/${id}/backtest-history?limit=${limit}`),
      saveBacktestHistory: (id: number, data: UnknownRecord) => fetchApi<UnknownRecord>(`/strategy-templates/${id}/backtest-history`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
    },
  },
  llmAnalysis: {
      getConfig: () =>
        fetchApi<{
          configured: boolean;
          available: boolean;
          provider: string | null;
          model: string | null;
          base_url?: string;
          error?: string;
          message?: string;
          selection_mode?: string;
        }>("/llm-analysis/config"),
      healthCheck: (options: LlmRuntimeOptions = {}) => {
        const query = new URLSearchParams()
        if (options.model) query.set("model", options.model)
        if (options.provider_type) query.set("provider_type", options.provider_type)
        if (options.base_url) query.set("base_url", options.base_url)
        const suffix = query.toString() ? `?${query.toString()}` : ""
        return fetchApi<{ status: string; provider: string; model?: string | null; base_url?: string | null; response_preview: string }>(
          `/llm-analysis/health-check${suffix}`
        )
      },
      dashboard: (data: { tickers: string[]; market?: string; include_market_review?: boolean } & LlmRuntimeOptions) =>
        fetchApi<{ results: LlmDecisionResult[]; summary?: LlmDashboardSummary; market_review?: MarketReviewResponse; market_review_error?: string }>("/llm-analysis/dashboard", {
          method: "POST",
          body: JSON.stringify(data),
        }),
    runDaily: (tickers?: string[]) =>
      fetchApi<UnknownRecord>("/llm-analysis/run-daily", {
        method: "POST",
        body: JSON.stringify(tickers ? { tickers } : {}),
      }),
    backtest: (ticker: string, horizon_days: number = 5) =>
      fetchApi<LlmBacktestResponse>(`/llm-analysis/backtest?ticker=${encodeURIComponent(ticker)}&horizon_days=${horizon_days}`),
  },
  agent: {
    research: (data: { query: string; model?: string | null }) =>
      fetchApi<AgentResearchResponse>("/agent/research", {
        method: "POST",
        body: JSON.stringify(data),
      }),
  },
  market: {
    dailyReview: (market: string = "cn") =>
      fetchApi<MarketReviewResponse>(`/market/daily-review?market=${market}`),
  },
  // --- Portfolio Analysis ---
  portfolio: {
    analyze: (data: { holdings: { ticker: string; shares: number; cost_price?: number }[] }) =>
      fetchApi<PortfolioAnalyzeResponse>("/portfolio/analyze", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    getDecision: (ticker: string) =>
      fetchApi<DecisionDashboardResult>(`/portfolio/decision/${ticker}`),
    getAssetType: (ticker: string) =>
      fetchApi<AssetTypeResponse>(`/portfolio/asset-type/${ticker}`),
  },
  // --- User Configuration ---
  user: {
    getWatchlist: () =>
      fetchApi<{ watchlist: string[]; count: number }>("/user/watchlist"),
    addWatchlist: (ticker: string, note?: string) =>
      fetchApi<{ success: boolean; ticker: string }>("/user/watchlist", {
        method: "POST",
        body: JSON.stringify({ ticker, note }),
      }),
    removeWatchlist: (ticker: string) =>
      fetchApi<{ success: boolean; ticker: string }>(`/user/watchlist/${ticker}`, {
        method: "DELETE",
      }),
    getPreferences: () =>
      fetchApi<UnknownRecord>("/user/preferences"),
    savePreferences: (data: { default_strategy?: string; risk_tolerance?: string; notification_enabled?: boolean }) =>
      fetchApi<{ success: boolean; preferences: UnknownRecord }>("/user/preferences", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    getStrategies: () =>
      fetchApi<{ strategies: { strategy_name: string; config: UnknownRecord }[] }>("/user/strategies"),
    saveStrategy: (strategyName: string, config: UnknownRecord) =>
      fetchApi<{ success: boolean; strategy_name: string }>(`/user/strategies/${strategyName}`, {
        method: "POST",
        body: JSON.stringify({ config }),
      }),
    assets: {
      getOverview: (syncDca: boolean = true, options?: RequestInit) =>
        fetchApi<UserAssetOverview>(`/user/assets?sync_dca=${syncDca ? "true" : "false"}`, options),
      upsert: (data: UserAssetUpsertRequest) =>
        fetchApi<UserAssetOverview>("/user/assets", {
          method: "POST",
          body: JSON.stringify(data),
        }),
      update: (ticker: string, data: UserAssetUpsertRequest) =>
        fetchApi<UserAssetOverview>(`/user/assets/${encodeURIComponent(ticker)}`, {
          method: "PUT",
          body: JSON.stringify(data),
        }),
      remove: (ticker: string) =>
        fetchApi<{ success: boolean; ticker: string }>(`/user/assets/${encodeURIComponent(ticker)}`, {
          method: "DELETE",
        }),
      getTransactions: (ticker?: string, options?: RequestInit) =>
        fetchApi<{ transactions: UserAssetTransaction[]; count: number }>(
          `/user/assets/transactions${ticker ? `?ticker=${encodeURIComponent(ticker)}` : ""}`,
          options
        ),
      addTransaction: (
        ticker: string,
        data: {
          transaction_type: "BUY" | "SELL" | "ADJUSTMENT_IN" | "ADJUSTMENT_OUT";
          quantity: number;
          price?: number;
          amount?: number;
          fee?: number;
          trade_date?: string;
          note?: string;
        }
      ) =>
        fetchApi<UserAssetOverview>(`/user/assets/${encodeURIComponent(ticker)}/transactions`, {
          method: "POST",
          body: JSON.stringify(data),
        }),
      reconcile: () =>
        fetchApi<UserAssetOverview & { reconcile: { created: number; rules_checked: number; as_of: string } }>(
          "/user/assets/reconcile",
          {
            method: "POST",
          }
        ),
    },
  },
  // --- System Monitoring ---
  monitoring: {
    getHealth: () => fetchApi<{ status: string; data: HealthCheckResult }>("/monitoring/health"),
    getMetrics: () => fetchApi<{ status: string; data: SystemMetrics }>("/monitoring/metrics"),
    getDetailedMetrics: () => fetchApi<{ status: string; data: DetailedSystemMetrics }>("/monitoring/metrics/detailed"),
    getMetricsHistory: (metricName: string, minutes: number = 60) =>
      fetchApi<{ status: string; data: { metric_name: string; minutes: number; history: UnknownArray } }>(
        `/monitoring/metrics/history?metric_name=${metricName}&minutes=${minutes}`
      ),
    getMetricStatistics: (windowMinutes: number = 60) =>
      fetchApi<{ status: string; data: UnknownRecord }>(`/monitoring/metrics/statistics?window_minutes=${windowMinutes}`),
    getSystemSummary: () => fetchApi<{ status: string; data: UnknownRecord }>("/monitoring/summary"),
    getMonitoringStatus: () => fetchApi<{ status: string; data: { metrics_collected?: number; health_checks?: number } & UnknownRecord }>("/monitoring/status"),
    getAlertRules: () => fetchApi<{ status: string; data: UnknownRecord[] }>("/monitoring/alert/rules"),
    getAlertChannels: () => fetchApi<{ status: string; data: UnknownRecord[] }>("/monitoring/alert/channels"),
    testAlertChannel: (channelType: string, config: UnknownRecord) =>
      fetchApi<{ status: string; message: string; data: UnknownRecord }>("/monitoring/alert/test", {
        method: "POST",
        body: JSON.stringify({ channel_type: channelType, config }),
      }),
    getAlertHistory: (limit: number = 100, severity?: string) =>
      fetchApi<{ status: string; data: AlertHistoryItem[] }>(
        `/monitoring/alert/history?limit=${limit}${severity ? `&severity=${severity}` : ""}`
      ),
    getAlertStatistics: () => fetchApi<{ status: string; data: AlertStatistics }>("/monitoring/alert/statistics"),
    restartMonitoring: () => fetchApi<{ status: string; message: string; data: UnknownRecord }>("/monitoring/restart", { method: "POST" }),
    getConfig: () => fetchApi<{ status: string; data: UnknownRecord }>("/monitoring/config"),
  },
};

// --- LLM Decision / Market Review Types ---
export interface LlmDashboardSummary {
  total: number;
  buy: number;
  watch: number;
  sell: number;
  avg_score?: number | null;
}
export interface LlmDecisionItem {
  ticker: string;
  name?: string;
  decision: {
    conclusion?: string;
    action?: string;
    score?: number;
    buy_price?: number | null;
    stop_loss?: number | null;
    target_price?: number | null;
    latest_price?: number;
    latest_rsi?: number;
    checklist?: { item?: string; condition?: string; status: string; value?: string }[];
    highlights?: string[];
    risks?: string[];
  };
  meta?: Record<string, unknown>;
}
export type LlmDecisionResult = LlmDecisionItem;

export interface LlmBacktestMetrics {
  sample_count: number;
  direction_win_rate?: number | null;
  take_profit_hit_rate?: number | null;
  stop_loss_hit_rate?: number | null;
}

export interface LlmBacktestDecisionRow {
  date: string;
  action?: string | null;
  buy_price?: number | null;
  stop_loss?: number | null;
  target_price?: number | null;
  score?: number | null;
  direction_correct?: boolean | null;
  take_profit_hit?: boolean | null;
  stop_loss_hit?: boolean | null;
  start_price: number;
  end_price: number;
  horizon_days: number;
}

export interface LlmBacktestResponse {
  ticker: string;
  metrics: LlmBacktestMetrics;
  decisions: LlmBacktestDecisionRow[];
}

// --- Agent Research ---
export interface AgentResearchResult {
  answer: string;
  iterations: number;
  tools_used: string[];
  tool_results: { name: string; args: Record<string, unknown>; data: Record<string, unknown> }[];
  scratchpad_path?: string | null;
}

export type AgentResearchResponse = AgentResearchResult;

// --- Market Review Interfaces ---

export interface MarketIndex {
  name: string;
  value: number;
  pct_change: number;
  volume?: number | null;
  amount?: number | null;
  amplitude?: number | null;
  turn_rate?: number | null;
}

export interface MarketOverview {
  up?: number | null;
  down?: number | null;
  limit_up?: number | null;
  limit_down?: number | null;
  amplitude?: number | null;
  turn_rate?: number | null;
}

export interface SectorInfo {
  name: string;
  pct_change: number;
}

export interface NorthBoundInfo {
  net_inflow?: number | null;
  unit?: string;
  description?: string;
}

export interface MarketReviewResponse {
  date: string;
  market: string;
  indices?: MarketIndex[];
  overview?: MarketOverview;
  sectors?: { gain?: SectorInfo[]; loss?: SectorInfo[] };
  northbound?: NorthBoundInfo;
}

// --- Backtest v1.2.0 Interfaces ---

export interface MultiStrategyRequest {
  strategies: Record<string, { weight: number; params: UnknownRecord }>;
  tickers: string[];
  start_date: string;
  end_date?: string;
  initial_capital?: number;
  benchmark_ticker?: string;
}

export interface ParameterOptimizationRequest {
  strategy_id: string;
  tickers: string[];
  param_grid: Record<string, unknown[]>;
  start_date: string;
  end_date?: string;
  initial_capital?: number;
  objective?: string;
  cv_days?: number;
}

export interface OptimizationResult {
  best_params: UnknownRecord;
  best_score: number;
  objective: string;
  all_results: Array<{ params: string; params_dict: UnknownRecord; score: number }>;
  best_result?: {
    metrics: Record<string, number>;
    equity_curve: unknown[];
  };
}

export interface BacktestExtendedMetrics {
  total_return: number;
  annual_return: number;
  annual_volatility: number;
  sharpe_ratio: number;
  information_ratio: number;
  max_drawdown: number;
  sortino_ratio: number;
  calmar_ratio: number;
  beta: number;
  alpha: number;
  r_squared: number;
  tracking_error: number;
}

export interface BacktestExtendedAnalysis {
  metrics: BacktestExtendedMetrics;
  drawdown_analysis: {
    details: Array<{ start_date: string; end_date: string; duration: number; depth: number }>;
    summary: Record<string, string>;
  };
  trade_analysis: UnknownRecord;
  monthly_returns: Array<{ year: number; month: number; return_rate: number; is_positive: boolean }>;
  best_month?: { year: number; month: number; return_rate: number };
  worst_month?: { year: number; month: number; return_rate: number };
  position_concentration: UnknownRecord;
}

export interface ComparativeAnalysis {
  comparison_table: Array<UnknownRecord>;
  summary: {
    best_sharpe: number;
    best_return: number;
    lowest_drawdown: number;
  };
}

// --- System Monitoring Interfaces ---

export interface SystemMetrics {
  timestamp?: string;
  cpu_usage: number;
  memory_usage: number;
  memory_used_mb: number;
  memory_available_mb: number;
  disk_usage: number;
  disk_free_gb: number;
  network_bytes_sent: number;
  network_bytes_recv: number;
  process_cpu_usage: number;
  process_memory_mb: number;
  data_update_latency: number;
  order_execution_latency: number;
  api_response_time: number;
}

export interface DetailedSystemMetrics {
  timestamp: string;
  system: {
    cpu_times?: {
      user: number;
      system: number;
      idle: number;
      iowait?: number | null;
    };
    memory: {
      total_mb: number;
      available_mb: number;
      used_mb: number;
      percent: number;
      active_mb?: number | null;
      inactive_mb?: number | null;
    };
  };
  process: {
    memory: {
      rss_mb: number;
      vms_mb: number;
    };
    cpu: {
      percent: number;
      num_threads: number;
    };
    open_files: number;
    connections: number;
  };
  storage: {
    disk: {
      total_gb: number;
      used_gb: number;
      free_gb: number;
      percent: number;
    };
    partitions?: Array<{
      device: string;
      mountpoint: string;
      fstype: string;
    }>;
  };
  network: {
    io: {
      bytes_sent: number;
      bytes_recv: number;
      packets_sent: number;
      packets_recv: number;
    };
    interfaces?: string[];
  };
  business: {
    data_update_latency: number;
    data_update_latency_minutes: number;
    order_execution_latency: number;
    api_response_time: number;
  };
}

export interface HealthCheckResult {
  status: "healthy" | "degraded" | "unhealthy" | "unknown";
  timestamp: string;
  checks: {
    [key: string]: {
      status: string;
      message: string;
      details: UnknownRecord;
    };
  };
}

export interface AlertHistoryItem {
  alert_id: string;
  rule_name: string;
  severity: string;
  message: string;
  metric_name: string;
  metric_value: number;
  threshold: number;
  timestamp: string;
  aggregate_count: number;
  channels: string[];
}

export interface AlertStatistics {
  total_alerts: number;
  by_severity: {
    info: number;
    warning: number;
    error: number;
    critical: number;
  };
  by_rule: Record<string, number>;
  active_rules: number;
  recent_alerts_24h: number;
  recent_alerts_1h: number;
  alerts_today: number;
}
