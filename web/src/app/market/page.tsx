"use client"

import { useState, useEffect, useMemo } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { api as apiClient, PricePoint, Asset } from "@/lib/api"
import { GlassCard, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { 
  ComposedChart, 
  Line, 
  Area, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer, 
  Legend,
  ReferenceLine,
  Cell,
  AreaChart,
  BarChart
} from "recharts"
import { 
  Brain, 
  Activity, 
  AlertTriangle, 
  Table as TableIcon, 
  LineChart as ChartIcon,
  Eye,
  EyeOff,
  Download,
  RefreshCw,
  TrendingUp,
  TrendingDown,
  Target,
} from "lucide-react"
import { HelpTooltip } from "@/components/ui/tooltip"
import { GLOSSARY } from "@/lib/glossary"
import { cn, formatPercent, formatCurrency } from "@/lib/utils"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"

// --- Technical Analysis Utils ---
function calculateSMA(data: number[], period: number) {
  const sma = new Array(data.length).fill(null);
  for (let i = period - 1; i < data.length; i++) {
    const sum = data.slice(i - period + 1, i + 1).reduce((a, b) => a + b, 0);
    sma[i] = sum / period;
  }
  return sma;
}

function calculateEMA(data: number[], period: number) {
  const ema = new Array(data.length).fill(null);
  const k = 2 / (period + 1);
  let prevEma = data[0];
  ema[0] = prevEma; // Simple initialization
  for (let i = 1; i < data.length; i++) {
    prevEma = data[i] * k + prevEma * (1 - k);
    ema[i] = prevEma;
  }
  return ema;
}

function calculateRSI(data: number[], period: number = 14) {
  const rsi = new Array(data.length).fill(null);
  let gains = 0;
  let losses = 0;

  // First period
  for (let i = 1; i <= period; i++) {
    const diff = data[i] - data[i - 1];
    if (diff >= 0) gains += diff;
    else losses -= diff;
  }
  
  let avgGain = gains / period;
  let avgLoss = losses / period;
  
  rsi[period] = 100 - (100 / (1 + avgGain / avgLoss));

  for (let i = period + 1; i < data.length; i++) {
    const diff = data[i] - data[i - 1];
    const gain = diff > 0 ? diff : 0;
    const loss = diff < 0 ? -diff : 0;
    
    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;
    
    rsi[i] = 100 - (100 / (1 + avgGain / avgLoss));
  }
  return rsi;
}

function calculateBollinger(data: number[], period: number = 20, multiplier: number = 2) {
  const bands = new Array(data.length).fill(null);
  for (let i = period - 1; i < data.length; i++) {
    const slice = data.slice(i - period + 1, i + 1);
    const mean = slice.reduce((a, b) => a + b, 0) / period;
    const variance = slice.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / period;
    const stdDev = Math.sqrt(variance);
    bands[i] = {
      upper: mean + multiplier * stdDev,
      middle: mean,
      lower: mean - multiplier * stdDev
    };
  }
  return bands;
}

function calculateMACD(data: number[]) {
  const ema12 = calculateEMA(data, 12);
  const ema26 = calculateEMA(data, 26);
  const macdLine = ema12.map((v, i) => (v !== null && ema26[i] !== null) ? v - ema26[i] : null);
  
  // Calculate Signal line (EMA9 of MACD line)
  // We need to filter nulls first but keep indices aligned? It's tricky with nulls.
  // Simplified: start after 26 periods
  const signalLine = new Array(data.length).fill(null);
  const validMacdStartIndex = 26; 
  if (data.length > validMacdStartIndex) {
      // Calculate EMA9 of the valid MACD part
      const validMacd = macdLine.slice(validMacdStartIndex) as number[];
      const validSignal = calculateEMA(validMacd, 9);
      for(let i=0; i<validSignal.length; i++) {
          signalLine[validMacdStartIndex + i] = validSignal[i];
      }
  }
  
  return macdLine.map((v, i) => ({
      macd: v,
      signal: signalLine[i],
      histogram: (v !== null && signalLine[i] !== null) ? v - signalLine[i] : null
  }));
}

// --- Design System Constants (Skeuominimalism) ---
const COLORS = {
  up: "#DC2626",   // Muted red for Up (China)
  down: "#059669", // Muted green for Down (China)
  neutral: "rgba(0, 0, 0, 0.3)",
  grid: "rgba(0, 0, 0, 0.04)",
  tooltipBg: "rgba(255, 255, 255, 0.94)",
  tooltipBorder: "rgba(0, 0, 0, 0.06)",
  historyLine: "#3B82F6", // Blue
  forecastLine: "#F59E0B", // Amber
}

const tooltipStyle = {
  backgroundColor: COLORS.tooltipBg,
  border: `1px solid ${COLORS.tooltipBorder}`,
  borderRadius: '10px',
  backdropFilter: 'blur(20px)',
  boxShadow: '0 4px 16px rgba(0, 0, 0, 0.08)',
  color: '#1A1A1A',
  fontSize: '12px',
}

const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.06, delayChildren: 0.1 }
  }
}

const item = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.16, 1, 0.3, 1] as const } }
}

export default function MarketAnalysisPage() {
  // --- State ---
  const [assets, setAssets] = useState<Asset[]>([])
  const [selectedTicker, setSelectedTicker] = useState("013281")
  const [forecastHorizon, setForecastHorizon] = useState("5")
  const [selectedModel, setSelectedModel] = useState("xgboost")
  const [lookbackDays, setLookbackDays] = useState("180")
  const [forecastData, setForecastData] = useState<{
    ticker: string
    predictions: Array<PricePoint & { lower?: number; upper?: number; type: 'history' | 'forecast' }>
  } | null>(null)
  
  const [loading, setLoading] = useState(false)
  const [mounted, setMounted] = useState(false)
  const [viewMode, setViewMode] = useState<'chart' | 'table'>('chart')
  const [showConfidence, setShowConfidence] = useState(true)

  // --- Effects ---
  useEffect(() => {
    setMounted(true)
    apiClient.stz.getAssetPool().then((res) => {
      if (res && res.length > 0) {
        setAssets(res)
        setSelectedTicker(res[0].ticker)
      } else {
        setAssets([
           { ticker: "013281", name: "国泰海通30天滚动持有中短债债券A", alias: "" },
           { ticker: "002611", name: "博时黄金ETF联接C", alias: "" },
           { ticker: "160615", name: "鹏华沪深300ETF联接(LOF)A", alias: "" },
           { ticker: "016858", name: "国金量化多因子股票C", alias: "" },
           { ticker: "159755", name: "电池ETF", alias: "" },
           { ticker: "006810", name: "泰康港股通中证香港银行投资指数C", alias: "" }
        ])
      }
    }).catch(console.error)
  }, [])

  // --- Handlers ---
  const handlePredict = async () => {
    setLoading(true)
    setForecastData(null) // Clear previous data
    try {
      // 1. Fetch history
      const historyRes = await apiClient.data.getPrices([selectedTicker], parseInt(lookbackDays));
      const historyPoints = historyRes.data[selectedTicker] || [];
      
      // 2. Fetch prediction
      const res = await apiClient.forecasting.getPrediction(
        selectedTicker, 
        parseInt(forecastHorizon), 
        selectedModel,
        parseInt(lookbackDays)
      )
      
      // Even if one fails, we might still want to show what we have, but let's assume both are needed.
      if (historyPoints.length > 0 && res && res.predictions) {
        // Calculate mock confidence intervals if not provided (simple spread)
        const combinedData = [
          ...historyPoints.map(p => ({ 
            ...p, 
            type: 'history' as const,
            upper: p.price, // History has no spread
            lower: p.price
          })),
          ...res.predictions.map((p: PricePoint, i) => {
            // Widen confidence interval over time
            const spreadFactor = 0.02 + (i * 0.005); 
            return {
              date: p.date,
              price: p.price,
              lower: p.price * (1 - spreadFactor),
              upper: p.price * (1 + spreadFactor),
              type: 'forecast' as const
            }
          })
        ];

        setForecastData({
          ticker: selectedTicker,
          predictions: combinedData
        })
      } else {
         console.error("Missing data for visualization", { historyPoints: historyPoints.length, predictions: res?.predictions?.length });
      }
    } catch (e) {
      console.error("Prediction failed:", e)
    } finally {
      setLoading(false)
    }
  }

  const [selectedIndicators, setSelectedIndicators] = useState({
    sma20: true,
    sma50: false,
    bollinger: true,
    rsi: true,
    macd: false
  })

  // --- Derived Metrics ---
  const metrics = useMemo(() => {
    if (!forecastData || !forecastData.predictions.length) return null;
    
    const history = forecastData.predictions.filter(p => p.type === 'history');
    const forecast = forecastData.predictions.filter(p => p.type === 'forecast');
    
    if (!history.length || !forecast.length) return null;

    const lastHistPrice = history[history.length - 1]?.price || 0;
    const finalPredPrice = forecast[forecast.length - 1]?.price || 0;
    
    const priceChange = finalPredPrice - lastHistPrice;
    const percentChange = (priceChange / lastHistPrice) * 100;
    const isBullish = priceChange > 0;
    
    // Volatility
    const returns = [];
    for (let i = 1; i < history.length; i++) {
      returns.push((history[i].price - history[i-1].price) / history[i-1].price);
    }
    const mean = returns.reduce((a, b) => a + b, 0) / (returns.length || 1);
    const variance = returns.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / (returns.length || 1);
    const stdDev = Math.sqrt(variance) * 100;

    let riskLevel = 'Low';
    let riskColor = COLORS.down; // Green is good/low risk
    if (stdDev > 2.5) { riskLevel = 'High'; riskColor = COLORS.up; } // Red is high risk
    else if (stdDev > 1) { riskLevel = 'Medium'; riskColor = '#F59E0B'; }

    return {
      lastHistPrice,
      finalPredPrice,
      priceChange,
      percentChange,
      isBullish,
      stdDev,
      riskLevel,
      riskColor
    };
  }, [forecastData]);

  // --- Technical Indicators Data ---
  const indicatorData = useMemo(() => {
    if (!forecastData || !forecastData.predictions) return [];
    
    // Use history data for calculations
    const history = forecastData.predictions.filter(p => p.type === 'history');
    if (history.length < 30) return []; // Need minimum data

    const prices = history.map(p => p.price);
    const sma20 = calculateSMA(prices, 20);
    const sma50 = calculateSMA(prices, 50);
    const bollinger = calculateBollinger(prices, 20, 2);
    const rsi = calculateRSI(prices, 14);
    const macd = calculateMACD(prices);

    return history.map((p, i) => ({
      ...p,
      sma20: sma20[i],
      sma50: sma50[i],
      bollingerUpper: bollinger[i]?.upper,
      bollingerMiddle: bollinger[i]?.middle,
      bollingerLower: bollinger[i]?.lower,
      rsi: rsi[i],
      macd: macd[i]?.macd,
      macdSignal: macd[i]?.signal,
      macdHist: macd[i]?.histogram
    })).filter(d => d.sma20 !== null); // Cut off initial nulls for cleaner chart
  }, [forecastData]);

  // --- Risk Metrics Data ---
  const riskMetrics = useMemo(() => {
    if (!forecastData || !forecastData.predictions) return null;
    const history = forecastData.predictions.filter(p => p.type === 'history');
    if (history.length < 30) return null;

    const prices = history.map(p => p.price);
    const returns = [];
    for(let i=1; i<prices.length; i++) {
        returns.push((prices[i] - prices[i-1]) / prices[i-1]);
    }

    // Max Drawdown
    let peak = -Infinity;
    let maxDrawdown = 0;
    const drawdownData = prices.map(p => {
        if (p > peak) peak = p;
        const dd = (peak - p) / peak;
        if (dd > maxDrawdown) maxDrawdown = dd;
        return { price: p, drawdown: -dd };
    });

    // Sharpe (simplified, assuming 0 risk free)
    const meanReturn = returns.reduce((a,b)=>a+b,0) / returns.length;
    const stdDevReturn = Math.sqrt(returns.reduce((a,b)=>a+Math.pow(b-meanReturn,2),0) / returns.length);
    const annualizedVol = stdDevReturn * Math.sqrt(252);
    const sharpe = annualizedVol !== 0 ? (meanReturn * 252) / annualizedVol : 0;

    // Sortino (simplified)
    const negativeReturns = returns.filter(r => r < 0);
    const downsideDev = Math.sqrt(negativeReturns.reduce((a,b)=>a+Math.pow(b,2),0) / returns.length); // Target 0
    const annualizedDownsideVol = downsideDev * Math.sqrt(252);
    const sortino = annualizedDownsideVol !== 0 ? (meanReturn * 252) / annualizedDownsideVol : 0;

    // Win Rate (Days)
    const upDays = returns.filter(r => r > 0).length;
    const winRate = upDays / returns.length;

    // Histogram data (simple bins)
    const bins = 20;
    const minRet = Math.min(...returns);
    const maxRet = Math.max(...returns);
    const range = maxRet - minRet;
    const step = range / bins;
    const distribution = Array(bins).fill(0).map((_, i) => ({
        range: `${((minRet + i*step)*100).toFixed(1)}%`,
        count: 0
    }));
    returns.forEach(r => {
        let idx = Math.floor((r - minRet) / step);
        if (idx >= bins) idx = bins - 1;
        distribution[idx].count++;
    });

    return {
        maxDrawdown,
        sharpe,
        sortino,
        volatility: annualizedVol,
        winRate,
        drawdownData,
        distribution
    };
  }, [forecastData]);

  // --- UI Components ---
  
  return (
    <motion.div 
      variants={container}
      initial="hidden"
      animate="show"
      className="space-y-6 max-w-7xl mx-auto"
    >
      {/* Header */}
      <motion.div variants={item} className="flex justify-between items-end">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-[-0.02em] text-foreground/90">
            AI 市场分析
          </h1>
          <p className="text-[13px] text-foreground/40">
            多维度智能金融市场分析平台
          </p>
        </div>
        <div className="flex gap-2">
           <Button variant="outline" size="sm" onClick={() => window.location.reload()}>
             <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
             刷新
           </Button>
           <Button variant="outline" size="sm" onClick={() => alert("导出功能开发中")}>
             <Download className="w-3.5 h-3.5 mr-1.5" />
             导出
           </Button>
        </div>
      </motion.div>

      {/* Main Content Area */}
      <Tabs defaultValue="forecast" className="space-y-6">
        
        {/* Top-level Tabs Navigation */}
        <motion.div variants={item}>
          <TabsList className="w-full justify-start h-auto">
            <TabsTrigger value="forecast" className="gap-1.5">
              <Brain className="h-3.5 w-3.5" /> AI 预测
            </TabsTrigger>
            <TabsTrigger value="indicators" className="gap-1.5">
              <Activity className="h-3.5 w-3.5" /> 技术指标
            </TabsTrigger>
            <TabsTrigger value="risk" className="gap-1.5">
              <AlertTriangle className="h-3.5 w-3.5" /> 风险分析
            </TabsTrigger>
          </TabsList>
        </motion.div>

        {/* AI Forecast Tab Content */}
        <TabsContent value="forecast" className="space-y-6 focus-visible:outline-none focus-visible:ring-0">
          
          {/* Control Bar (Moved Inside) */}
          <motion.div variants={item}>
            <GlassCard className="!p-4 flex flex-wrap gap-4 items-end">
               {/* Asset */}
               <div className="space-y-1.5 min-w-[180px] flex-1">
                  <label className="text-[11px] font-medium text-foreground/40 uppercase tracking-wider flex items-center gap-1">
                    {GLOSSARY.Asset.term} <HelpTooltip content={GLOSSARY.Asset.definition} />
                  </label>
                  <Select value={selectedTicker} onValueChange={setSelectedTicker}>
                    <SelectTrigger className="h-9">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {assets.map(a => (
                        <SelectItem key={a.ticker} value={a.ticker}>{a.alias || a.name || a.ticker}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
               </div>

               {/* Model */}
               <div className="space-y-1.5 min-w-[140px]">
                  <label className="text-[11px] font-medium text-foreground/40 uppercase tracking-wider flex items-center gap-1">
                    {GLOSSARY.Model.term} <HelpTooltip content={GLOSSARY.Model.definition} />
                  </label>
                  <Select value={selectedModel} onValueChange={setSelectedModel}>
                    <SelectTrigger className="h-9">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="xgboost">XGBoost</SelectItem>
                      <SelectItem value="prophet">Prophet</SelectItem>
                      <SelectItem value="lstm">LSTM</SelectItem>
                      <SelectItem value="random_forest">Random Forest</SelectItem>
                      <SelectItem value="lightgbm">LightGBM</SelectItem>
                    </SelectContent>
                  </Select>
               </div>

               {/* Lookback */}
               <div className="space-y-1.5 min-w-[120px]">
                  <label className="text-[11px] font-medium text-foreground/40 uppercase tracking-wider flex items-center gap-1">
                    {GLOSSARY.LookbackDays.term} <HelpTooltip content={GLOSSARY.LookbackDays.definition} />
                  </label>
                  <Select value={lookbackDays} onValueChange={setLookbackDays}>
                    <SelectTrigger className="h-9">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {[7, 30, 60, 90, 180, 360, 720].map(d => (
                        <SelectItem key={d} value={d.toString()}>{d} 天</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
               </div>

               {/* Horizon */}
               <div className="space-y-1.5 min-w-[120px]">
                  <label className="text-[11px] font-medium text-foreground/40 uppercase tracking-wider flex items-center gap-1">
                    {GLOSSARY.Horizon.term} <HelpTooltip content={GLOSSARY.Horizon.definition} />
                  </label>
                  <Select value={forecastHorizon} onValueChange={setForecastHorizon}>
                    <SelectTrigger className="h-9">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {[1, 3, 5, 7, 15, 30].map(d => (
                        <SelectItem key={d} value={d.toString()}>{d} 天</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
               </div>

               <Button 
                onClick={handlePredict} 
                disabled={loading} 
                className="h-9 px-6"
               >
                 {loading ? (
                   <motion.div 
                     animate={{ rotate: 360 }} 
                     transition={{ repeat: Infinity, duration: 1 }}
                     className="mr-2"
                   >
                     <RefreshCw className="w-4 h-4" />
                   </motion.div>
                 ) : (
                   <Brain className="w-4 h-4 mr-2" />
                 )}
                 {loading ? "计算中..." : "开始预测"}
               </Button>
            </GlassCard>
          </motion.div>

          <motion.div variants={item} className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            
            {/* Main Chart Section (Spans 3 cols on lg, 2 on md, 1 on sm) */}
            <GlassCard className="lg:col-span-3 md:col-span-2 p-1 relative overflow-hidden group">
              {/* Chart Toolbar */}
              <div className="absolute top-4 right-4 z-20 flex items-center gap-1 glass-dropdown p-1 rounded-xl">
                <Button 
                  variant="ghost" 
                  size="icon" 
                  className="h-8 w-8"
                  onClick={() => setShowConfidence(!showConfidence)}
                  title="Toggle Confidence Interval"
                >
                  {showConfidence ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
                </Button>
                <div className="w-px h-4 bg-black/[0.06]" />
                <Button 
                  variant={viewMode === 'chart' ? 'secondary' : 'ghost'} 
                  size="icon" 
                  className="h-8 w-8"
                  onClick={() => setViewMode('chart')}
                >
                  <ChartIcon className="h-4 w-4" />
                </Button>
                <Button 
                  variant={viewMode === 'table' ? 'secondary' : 'ghost'} 
                  size="icon" 
                  className="h-8 w-8"
                  onClick={() => setViewMode('table')}
                >
                  <TableIcon className="h-4 w-4" />
                </Button>
              </div>

              {/* Content */}
              <div className="p-6 h-[350px] sm:h-[500px]">
                {!mounted || !forecastData ? (
                  <div className="h-full flex flex-col items-center justify-center text-muted-foreground gap-4">
                    <Brain className="w-16 h-16 opacity-20" />
                    <p>请选择标的并点击“开始预测”</p>
                  </div>
                ) : viewMode === 'chart' ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={forecastData.predictions}>
                      <defs>
                        <linearGradient id="colorForecast" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor={metrics?.isBullish ? COLORS.up : COLORS.down} stopOpacity={0.3}/>
                          <stop offset="95%" stopColor={metrics?.isBullish ? COLORS.up : COLORS.down} stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={COLORS.grid} />
                      <XAxis 
                        dataKey="date" 
                        tickFormatter={(v) => {
                          const d = new Date(v);
                          return `${d.getMonth()+1}/${d.getDate()}`;
                        }}
                        minTickGap={40}
                        stroke={COLORS.neutral}
                        fontSize={12}
                        tickLine={false}
                        axisLine={false}
                      />
                      <YAxis 
                        domain={['auto', 'auto']} 
                        stroke={COLORS.neutral}
                        fontSize={12}
                        tickLine={false}
                        axisLine={false}
                        tickFormatter={(v) => v.toFixed(2)}
                      />
                      <Tooltip 
                        contentStyle={tooltipStyle}
                        labelFormatter={(v) => new Date(v).toLocaleDateString()}
                        formatter={(value: any) => [Number(value).toFixed(2), '']}
                      />
                      <Legend />
                      
                      {/* Confidence Interval Area */}
                      {showConfidence && (
                        <Area
                          type="monotone"
                          dataKey="upper"
                          data={forecastData.predictions.filter(p => p.type === 'forecast')}
                          stroke="none"
                          fill={metrics?.isBullish ? COLORS.up : COLORS.down}
                          fillOpacity={0.1}
                          connectNulls
                        />
                      )}
                      
                      {/* History Line */}
                      <Line 
                        type="monotone" 
                        dataKey={(d) => d.type === 'history' ? d.price : null} 
                        stroke={COLORS.historyLine} 
                        strokeWidth={2} 
                        name="历史价格" 
                        dot={false}
                        connectNulls={false}
                      />
                      
                      {/* Forecast Line */}
                      <Line 
                        type="monotone" 
                        dataKey={(d) => d.type === 'forecast' ? d.price : null} 
                        stroke={metrics?.isBullish ? COLORS.up : COLORS.down} 
                        strokeWidth={2} 
                        name="AI 预测" 
                        dot={{ r: 3, strokeWidth: 1 }}
                        strokeDasharray="5 5"
                        connectNulls
                      />
                      
                      {/* Today Marker */}
                      <ReferenceLine 
                        x={forecastData.predictions.findLast(p => p.type === 'history')?.date} 
                        stroke={COLORS.neutral} 
                        strokeDasharray="3 3"
                        label={{ position: 'top', value: 'Today', fill: COLORS.neutral, fontSize: 10 }}
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-full overflow-auto pr-2">
                    <table className="w-full text-[13px]">
                      <thead className="sticky top-0 glass-dropdown z-10">
                        <tr className="border-b border-black/[0.04] text-left">
                          <th className="py-2 font-medium text-foreground/40 text-[12px] uppercase tracking-wider">日期</th>
                          <th className="py-2 font-medium text-foreground/40 text-[12px] uppercase tracking-wider">类型</th>
                          <th className="py-2 font-medium text-foreground/40 text-[12px] uppercase tracking-wider text-right">价格</th>
                          <th className="py-2 font-medium text-foreground/40 text-[12px] uppercase tracking-wider text-right">下限</th>
                          <th className="py-2 font-medium text-foreground/40 text-[12px] uppercase tracking-wider text-right">上限</th>
                        </tr>
                      </thead>
                      <tbody>
                        {[...forecastData.predictions].reverse().map((p, i) => (
                          <tr key={i} className="border-b border-black/[0.03] hover:bg-black/[0.02] transition-colors duration-150">
                            <td className="py-2 font-mono text-xs">{new Date(p.date).toLocaleDateString()}</td>
                            <td className="py-2">
                              <span className={cn(
                                "px-2 py-0.5 rounded-full text-[10px] uppercase font-bold",
                                p.type === 'history' ? "bg-blue-500/10 text-blue-500" : "bg-yellow-500/10 text-yellow-500"
                              )}>
                                {p.type === 'history' ? 'History' : 'Forecast'}
                              </span>
                            </td>
                            <td className="py-2 text-right font-mono">{p.price.toFixed(2)}</td>
                            <td className="py-2 text-right font-mono text-muted-foreground">{p.lower?.toFixed(2)}</td>
                            <td className="py-2 text-right font-mono text-muted-foreground">{p.upper?.toFixed(2)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </GlassCard>

            {/* Metrics Sidebar (Spans 1 col on lg, 2 on md, 1 on sm) */}
            <div className="flex flex-col gap-6 lg:col-span-1 md:col-span-2">
              
              {/* Trend Card */}
              <GlassCard className="flex-1 flex flex-col justify-center p-6 relative overflow-hidden">
                <div className="absolute top-0 right-0 p-3 opacity-10">
                  {metrics?.isBullish ? <TrendingUp className="w-24 h-24" /> : <TrendingDown className="w-24 h-24" />}
                </div>
                <CardTitle className="text-sm font-medium text-muted-foreground mb-4">预测趋势 (Trend)</CardTitle>
                
                {!metrics ? (
                  <div className="text-2xl font-bold text-muted-foreground">---</div>
                ) : (
                  <>
                    <div className="flex items-baseline gap-2">
                      <span 
                        className="text-4xl font-bold tracking-tighter"
                        style={{ color: metrics.isBullish ? COLORS.up : COLORS.down }}
                      >
                        {metrics.isBullish ? "看涨" : "看跌"}
                      </span>
                      <span className="text-sm font-medium opacity-80 uppercase">
                        {metrics.isBullish ? "Bullish" : "Bearish"}
                      </span>
                    </div>
                    <div 
                      className="mt-2 text-sm font-mono flex items-center gap-1"
                      style={{ color: metrics.isBullish ? COLORS.up : COLORS.down }}
                    >
                      {metrics.isBullish ? '+' : ''}{metrics.percentChange.toFixed(2)}%
                      <span className="text-muted-foreground ml-1 text-xs">预期变动</span>
                    </div>
                  </>
                )}
              </GlassCard>

              {/* Target Card */}
              <GlassCard className="flex-1 flex flex-col justify-center p-6">
                <div className="absolute top-0 right-0 p-3 opacity-10">
                  <Target className="w-24 h-24" />
                </div>
                <CardTitle className="text-sm font-medium text-muted-foreground mb-4">目标价格 (Target)</CardTitle>
                
                {!metrics ? (
                  <div className="text-2xl font-bold text-muted-foreground">---</div>
                ) : (
                  <>
                    <div className="text-4xl font-bold tracking-tighter text-foreground font-mono">
                      {metrics.finalPredPrice.toFixed(2)}
                    </div>
                    <p className="mt-2 text-xs text-muted-foreground">
                      {forecastHorizon} 天后预期价格
                    </p>
                  </>
                )}
              </GlassCard>

              {/* Risk Card */}
              <GlassCard className="flex-1 flex flex-col justify-center p-6">
                 <CardTitle className="text-sm font-medium text-muted-foreground mb-4 flex items-center gap-2">
                   波动率风险
                   <HelpTooltip content={GLOSSARY.VolatilityRisk.definition} />
                 </CardTitle>
                 
                 {!metrics ? (
                   <div className="text-2xl font-bold text-muted-foreground">---</div>
                 ) : (
                   <>
                     <div 
                       className="text-3xl font-bold tracking-tight"
                       style={{ color: metrics.riskColor }}
                     >
                       {metrics.riskLevel === 'Low' && '低 (Low)'}
                       {metrics.riskLevel === 'Medium' && '中 (Medium)'}
                       {metrics.riskLevel === 'High' && '高 (High)'}
                     </div>
                     <p className="mt-2 text-xs text-muted-foreground font-mono">
                       历史波动率: {metrics.stdDev.toFixed(2)}%
                     </p>
                   </>
                 )}
              </GlassCard>
            </div>
          </motion.div>
        </TabsContent>

        {/* Technical Indicators Tab Content */}
        <TabsContent value="indicators" className="space-y-6 focus-visible:outline-none focus-visible:ring-0">
          <GlassCard className="p-6 relative overflow-hidden h-[450px] sm:h-[600px] flex flex-col">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mb-6 gap-4">
              <CardTitle className="text-lg">技术指标分析</CardTitle>
              <div className="flex flex-wrap gap-4 items-center">
                <div className="flex items-center space-x-2">
                  <Checkbox 
                    id="sma20" 
                    checked={selectedIndicators.sma20}
                    onCheckedChange={(c) => setSelectedIndicators(p => ({...p, sma20: !!c}))}
                  />
                  <Label htmlFor="sma20" className="text-xs">SMA 20</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <Checkbox 
                    id="sma50" 
                    checked={selectedIndicators.sma50}
                    onCheckedChange={(c) => setSelectedIndicators(p => ({...p, sma50: !!c}))}
                  />
                  <Label htmlFor="sma50" className="text-xs">SMA 50</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <Checkbox 
                    id="bollinger" 
                    checked={selectedIndicators.bollinger}
                    onCheckedChange={(c) => setSelectedIndicators(p => ({...p, bollinger: !!c}))}
                  />
                  <Label htmlFor="bollinger" className="text-xs">Bollinger</Label>
                </div>
                <div className="w-px h-4 bg-black/[0.06] mx-2" />
                <div className="flex items-center space-x-2">
                  <Checkbox 
                    id="rsi" 
                    checked={selectedIndicators.rsi}
                    onCheckedChange={(c) => setSelectedIndicators(p => ({...p, rsi: !!c}))}
                  />
                  <Label htmlFor="rsi" className="text-xs">RSI</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <Checkbox 
                    id="macd" 
                    checked={selectedIndicators.macd}
                    onCheckedChange={(c) => setSelectedIndicators(p => ({...p, macd: !!c}))}
                  />
                  <Label htmlFor="macd" className="text-xs">MACD</Label>
                </div>
              </div>
            </div>

            {indicatorData.length === 0 ? (
              <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground gap-4">
                <Activity className="w-16 h-16 opacity-20" />
                <p>数据不足或未加载，请先进行预测或增加回溯天数。</p>
              </div>
            ) : (
              <div className="flex-1 flex flex-col gap-4">
                {/* Main Price Chart */}
                <div className="flex-1 min-h-0">
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={indicatorData} margin={{ top: 5, right: 5, left: 0, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={COLORS.grid} />
                      <XAxis dataKey="date" tick={false} axisLine={false} />
                      <YAxis domain={['auto', 'auto']} orientation="right" tick={{fontSize: 10, fill: '#888'}} axisLine={false} tickLine={false} />
                      <Tooltip 
                        contentStyle={tooltipStyle}
                        labelFormatter={(v) => new Date(v).toLocaleDateString()}
                      />
                      <Legend wrapperStyle={{ fontSize: '11px' }} />
                      <Line type="monotone" dataKey="price" stroke="#64748B" dot={false} strokeWidth={1.5} name="Price" />
                      {selectedIndicators.sma20 && <Line type="monotone" dataKey="sma20" stroke="#F59E0B" dot={false} strokeWidth={1} name="SMA 20" />}
                      {selectedIndicators.sma50 && <Line type="monotone" dataKey="sma50" stroke="#3B82F6" dot={false} strokeWidth={1} name="SMA 50" />}
                      {selectedIndicators.bollinger && <Area type="monotone" dataKey="bollingerUpper" stroke="none" fill="#8B5CF6" fillOpacity={0.1} />}
                      {selectedIndicators.bollinger && <Area type="monotone" dataKey="bollingerLower" stroke="none" fill="#8B5CF6" fillOpacity={0.1} />}
                      {selectedIndicators.bollinger && <Line type="monotone" dataKey="bollingerUpper" stroke="#8B5CF6" strokeOpacity={0.3} dot={false} strokeWidth={1} name="Upper BB" />}
                      {selectedIndicators.bollinger && <Line type="monotone" dataKey="bollingerLower" stroke="#8B5CF6" strokeOpacity={0.3} dot={false} strokeWidth={1} name="Lower BB" />}
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>

                {/* Sub Charts */}
                {(selectedIndicators.rsi || selectedIndicators.macd) && (
                  <div className="h-[150px] border-t border-black/[0.04] pt-2">
                    <ResponsiveContainer width="100%" height="100%">
                      <ComposedChart data={indicatorData} margin={{ top: 5, right: 5, left: 0, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={COLORS.grid} />
                        <XAxis dataKey="date" tickFormatter={(v) => new Date(v).toLocaleDateString()} minTickGap={50} tick={{fontSize: 10, fill: '#888'}} axisLine={false} tickLine={false} />
                        <YAxis domain={selectedIndicators.rsi ? [0, 100] : ['auto', 'auto']} orientation="right" tick={{fontSize: 10, fill: '#888'}} axisLine={false} tickLine={false} width={40} />
                        <Tooltip contentStyle={tooltipStyle} />
                        
                        {selectedIndicators.rsi && (
                          <>
                            <ReferenceLine y={70} stroke="rgba(0,0,0,0.1)" strokeDasharray="3 3" />
                            <ReferenceLine y={30} stroke="rgba(0,0,0,0.1)" strokeDasharray="3 3" />
                            <Line type="monotone" dataKey="rsi" stroke="#EC4899" dot={false} strokeWidth={1.5} name="RSI" />
                          </>
                        )}

                        {selectedIndicators.macd && !selectedIndicators.rsi && (
                          <>
                            <Line type="monotone" dataKey="macd" stroke="#10B981" dot={false} strokeWidth={1} name="MACD" />
                            <Line type="monotone" dataKey="macdSignal" stroke="#F6465D" dot={false} strokeWidth={1} name="Signal" />
                            <Bar dataKey="macdHist" fill="#3B82F6" name="Hist" barSize={4}>
                                {indicatorData.map((entry, index) => (
                                    <Cell key={`cell-${index}`} fill={(entry.macdHist || 0) > 0 ? COLORS.up : COLORS.down} fillOpacity={0.5} />
                                ))}
                            </Bar>
                          </>
                        )}
                      </ComposedChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </div>
            )}
          </GlassCard>
        </TabsContent>

        {/* Risk Analysis Tab Content */}
        <TabsContent value="risk" className="space-y-6 focus-visible:outline-none focus-visible:ring-0">
          {!riskMetrics ? (
             <GlassCard className="p-12 flex flex-col items-center justify-center text-muted-foreground gap-4">
               <AlertTriangle className="w-16 h-16 opacity-20" />
               <p>风险数据不足，请先进行预测或增加回溯天数（建议 &gt; 30天）。</p>
             </GlassCard>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Metrics Overview */}
              <GlassCard className="md:col-span-3 grid grid-cols-2 md:grid-cols-4 gap-4 p-6">
                <div className="space-y-1">
                  <div className="text-xs text-muted-foreground uppercase tracking-wider">Sharpe Ratio</div>
                  <div className={cn("text-2xl font-bold", riskMetrics.sharpe > 1 ? "text-emerald-500" : "text-foreground")}>
                    {riskMetrics.sharpe.toFixed(2)}
                  </div>
                </div>
                <div className="space-y-1">
                  <div className="text-xs text-muted-foreground uppercase tracking-wider">Max Drawdown</div>
                  <div className="text-2xl font-bold text-red-500">
                    {formatPercent(riskMetrics.maxDrawdown)}
                  </div>
                </div>
                <div className="space-y-1">
                  <div className="text-xs text-muted-foreground uppercase tracking-wider">Volatility (Ann.)</div>
                  <div className="text-2xl font-bold">
                    {formatPercent(riskMetrics.volatility)}
                  </div>
                </div>
                <div className="space-y-1">
                  <div className="text-xs text-muted-foreground uppercase tracking-wider">Win Rate (Days)</div>
                  <div className="text-2xl font-bold text-emerald-500">
                    {formatPercent(riskMetrics.winRate)}
                  </div>
                </div>
              </GlassCard>

              {/* Drawdown Chart */}
              <GlassCard className="md:col-span-2 p-6 h-[300px]">
                <CardTitle className="text-sm font-medium text-muted-foreground mb-4">最大回撤走势 (Drawdown)</CardTitle>
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={riskMetrics.drawdownData}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={COLORS.grid} />
                    <XAxis dataKey="price" tick={false} axisLine={false} />
                    <YAxis tickFormatter={(v) => `${(v*100).toFixed(0)}%`} tick={{fontSize: 10, fill: '#888'}} axisLine={false} tickLine={false} />
                    <Tooltip 
                      contentStyle={tooltipStyle}
                      formatter={(v: any) => [formatPercent(Number(v)), 'Drawdown']}
                      labelFormatter={() => ''}
                    />
                    <Area type="step" dataKey="drawdown" stroke="#F6465D" fill="#F6465D" fillOpacity={0.2} strokeWidth={2} />
                  </AreaChart>
                </ResponsiveContainer>
              </GlassCard>

              {/* Returns Distribution */}
              <GlassCard className="p-6 h-[300px]">
                <CardTitle className="text-sm font-medium text-muted-foreground mb-4">收益分布 (Distribution)</CardTitle>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={riskMetrics.distribution}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={COLORS.grid} />
                    <XAxis dataKey="range" tick={{fontSize: 8, fill: '#888'}} interval={4} axisLine={false} tickLine={false} />
                    <Tooltip 
                      cursor={{fill: 'rgba(0,0,0,0.02)'}}
                      contentStyle={tooltipStyle}
                    />
                    <Bar dataKey="count" fill="#3B82F6" radius={[2, 2, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </GlassCard>
            </div>
          )}
        </TabsContent>
      </Tabs>
    </motion.div>
  )
}