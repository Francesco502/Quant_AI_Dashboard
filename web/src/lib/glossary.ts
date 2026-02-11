
export const GLOSSARY = {
  // 财务/账户相关
  TotalBalance: {
    term: "总资产 (Total Balance)",
    definition: "当前账户的总权益，包含可用现金和持有头寸的市值总和。"
  },
  DailyPnL: {
    term: "当日盈亏 (Daily P&L)",
    definition: "反映今日资产的盈亏情况。计算公式：(今日最新价 - 昨日收盘价) × 持仓数量。红色表示盈利，绿色表示亏损（遵循中国股市惯例）。"
  },
  ActiveStrategies: {
    term: "运行中策略 (Active Strategies)",
    definition: "当前已激活并正在后台运行扫描的量化策略数量。"
  },
  
  // 市场/预测相关
  Asset: {
    term: "标的 (Asset)",
    definition: "您希望进行分析和预测的金融标的（如股票、加密货币、指数等）。"
  },
  Model: {
    term: "模型 (Model)",
    definition: "用于生成价格预测的机器学习模型。不同模型适用于不同的市场环境（如 Prophet 擅长捕捉周期性，LSTM 擅长处理长期依赖）。"
  },
  LookbackDays: {
    term: "训练天数 (Lookback)",
    definition: "用于训练 AI 模型的历史数据长度。更多的数据通常能提供更稳定的长期趋势，但也可能包含过时的市场模式。"
  },
  Horizon: {
    term: "预测周期 (Horizon)",
    definition: "AI 模型向后预测的时间跨度（例如 5 天、10 天）。较短的周期（3-7天）通常具有较高的准确度，长周期更适合观察大趋势。"
  },
  ModelConfidence: {
    term: "模型置信度 (Model Confidence)",
    definition: "AI 模型对自己预测结果准确性的打分（0-100%）。该分数基于历史回测准确率、当前数据质量和市场波动特征综合计算得出。建议仅参考置信度 > 70% 的信号。"
  },
  VolatilityRisk: {
    term: "波动率风险 (Volatility Risk)",
    definition: "基于历史价格标准差计算的风险指标。高波动率意味着价格可能剧烈震荡，风险较高，但也可能带来更高的短期收益机会。"
  },
  TechnicalIndicators: {
    term: "技术指标 (Technical Indicators)",
    definition: "基于历史价格和成交量计算的数学辅助工具（如 RSI, MACD, KDJ），用于辅助判断市场的超买超卖状态或趋势强度。"
  },
  
  // 交易/信号相关
  SignalConfidence: {
    term: "信号置信度 (Confidence)",
    definition: "量化策略生成此交易信号的可信程度。通常结合了技术面因子的强度和 AI 模型预测评分。高置信度信号往往意味着多重指标共振。"
  },
  SignalStatus: {
    term: "状态 (Status)",
    definition: "信号的当前生命周期状态。Pending (待处理)：等待执行；Executed (已执行)：已提交订单；Expired (已过期)：信号超过时效未执行。"
  },
  
  // 系统设置相关
  PaperAccount: {
    term: "模拟账户 (Paper Account)",
    definition: "用于测试策略和练习交易的虚拟账户。资金是虚拟的，但行情数据是真实的。通过模拟交易验证策略有效性后再进行实盘。"
  },
  DataSources: {
    term: "数据源 (Data Sources)",
    definition: "系统获取市场行情数据的接口服务商（如 AkShare, Yahoo Finance）。建议配置多个数据源以保证数据的稳定性和完整性。"
  },
  
  // 回测相关
  SharpeRatio: {
    term: "夏普比率 (Sharpe Ratio)",
    definition: "风险调整后收益指标，计算公式为（策略收益率 - 无风险收益率）/ 收益率标准差。该指标越高，说明单位风险所获得的超额收益越多。通常 Sharpe > 1 被认为具有投资价值，> 2 则非常优秀。"
  },
  MaxDrawdown: {
    term: "最大回撤 (Max Drawdown)",
    definition: "投资组合在选定周期内从峰值到谷底的最大亏损幅度，计算公式为（峰值 - 谷底）/ 峰值。该指标反映策略最极端的亏损情况，是衡量风险的重要指标。通常建议控制在 20% 以内。"
  },
  TotalReturn: {
    term: "总收益率 (Total Return)",
    definition: "策略在回测期间累计获得的收益百分比，计算公式为（期末权益 - 期初权益）/ 期初权益 × 100%。该指标反映策略的整体盈利能力。"
  },
  Volatility: {
    term: "波动率 (Volatility)",
    definition: "通常指收益率的年化标准差，用于衡量策略收益的波动程度。高波动率意味着策略收益起伏较大，风险较高；低波动率则表示收益较为稳定。"
  },
  EquityCurve: {
    term: "权益曲线 (Equity Curve)",
    definition: "展示账户资金随时间变化的曲线图，横轴为时间，纵轴为账户权益值。通过观察权益曲线的平滑度、回撤幅度和增长趋势，可以直观评估策略的表现。"
  },
  
  // 技术指标相关
  SMA: {
    term: "简单移动平均线 (SMA)",
    definition: "Simple Moving Average，将最近 N 天的收盘价相加后除以 N 得到的平均值。SMA 能平滑价格波动，帮助识别趋势方向。常用周期有 5日、10日、20日、60日等。"
  },
  EMA: {
    term: "指数移动平均线 (EMA)",
    definition: "Exponential Moving Average，与 SMA 类似，但赋予近期价格更高的权重，因此对价格变化的反应更灵敏。EMA 比 SMA 更快捕捉趋势转折，但也更容易产生假信号。"
  },
  RSI: {
    term: "相对强弱指标 (RSI)",
    definition: "Relative Strength Index，衡量价格上涨和下跌的力度，取值范围 0-100。通常 RSI > 70 表示超买（可能回调），RSI < 30 表示超卖（可能反弹）。常用周期为 14 日。"
  },
  MACD: {
    term: "异同移动平均线 (MACD)",
    definition: "Moving Average Convergence Divergence，由快线（DIF）、慢线（DEA）和柱状图（MACD柱）组成。DIF 上穿 DEA 为买入信号（金叉），下穿为卖出信号（死叉）。"
  },
  Bollinger: {
    term: "布林带 (Bollinger Bands)",
    definition: "由中轨（通常是 20 日 SMA）、上轨（中轨 + 2 倍标准差）和下轨（中轨 - 2 倍标准差）组成。价格触及上轨可能超买，触及下轨可能超卖。布林带收窄预示波动可能加剧。"
  },
  WinRate: {
    term: "胜率 (Win Rate)",
    definition: "盈利交易次数占总交易次数的百分比。计算公式：盈利交易数 / 总交易数 × 100%。高胜率意味着策略大多数时候能正确判断方向，但不代表一定能盈利（还需考虑盈亏比）。"
  },
  Sortino: {
    term: "索提诺比率 (Sortino Ratio)",
    definition: "与夏普比率类似，但仅考虑下行波动（负收益的标准差）作为风险度量。相比夏普比率，索提诺比率更能反映策略对负面风险的控制能力。数值越高越好。"
  }
};
