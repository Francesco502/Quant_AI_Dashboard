"""
Apple Design System UI 组件
iPhone 16 Pro 风格的高端 UI 组件库
"""
import streamlit as st
import plotly.graph_objs as go
from typing import Optional, List, Dict, Any


# ==================== Apple 设计系统颜色 ====================
APPLE_COLORS = {
    'black': '#0A0A0B',
    'dark': '#1D1D1F',
    'gray_900': '#2D2D2F',
    'gray_800': '#3A3A3C',
    'gray_700': '#48484A',
    'gray_600': '#636366',
    'gray_500': '#8E8E93',
    'gray_400': '#AEAEB2',
    'gray_300': '#C7C7CC',
    'gray_200': '#D1D1D6',
    'gray_100': '#E5E5EA',
    'gray_50': '#F2F2F7',
    'white': '#FFFFFF',
    'blue': '#0071E3',
    'blue_light': '#409CFF',
    'blue_dark': '#0051A8',
    'green': '#30D158',
    'green_light': '#4CD964',
    'orange': '#FF9500',
    'red': '#FF453A',
    'purple': '#BF5AF2',
    'teal': '#64D2FF',
    'indigo': '#5E5CE6',
}


# ==================== Plotly 图表主题 ====================
def get_apple_chart_layout(
    title: str = "",
    height: int = 380,
    show_legend: bool = True,
    xaxis_title: str = "",
    yaxis_title: str = "",
) -> dict:
    """获取 Apple 风格的 Plotly 图表布局配置"""
    return dict(
        height=height,
        # 适当留白，确保图表边框完整显示
        margin=dict(l=50, r=25, t=50 if title else 30, b=45),
        title=dict(
            text=title,
            font=dict(
                family="Plus Jakarta Sans, -apple-system, BlinkMacSystemFont, sans-serif",
                size=20,
                color=APPLE_COLORS['dark'],
            ),
            x=0,
            xanchor='left',
        ) if title else None,
        xaxis_title=xaxis_title,
        yaxis_title=yaxis_title,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(
            family="Plus Jakarta Sans, -apple-system, BlinkMacSystemFont, sans-serif",
            size=13,
            color=APPLE_COLORS['gray_600'],
        ),
        xaxis=dict(
            showgrid=True,
            gridcolor='rgba(229, 229, 234, 0.5)',
            gridwidth=1,
            zeroline=False,
            showline=True,
            linecolor=APPLE_COLORS['gray_200'],
            linewidth=1,
            tickfont=dict(size=12, color=APPLE_COLORS['gray_500']),
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(229, 229, 234, 0.5)',
            gridwidth=1,
            zeroline=False,
            showline=True,
            linecolor=APPLE_COLORS['gray_200'],
            linewidth=1,
            tickfont=dict(size=12, color=APPLE_COLORS['gray_500']),
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor='rgba(255,255,255,0.9)',
            bordercolor=APPLE_COLORS['gray_100'],
            borderwidth=1,
            font=dict(size=12, color=APPLE_COLORS['gray_700']),
        ) if show_legend else None,
        showlegend=show_legend,
        # 使用普通 x 轴 hover，而不是 unified，避免 Plotly 在图左上角展示 "undefined" 等多余标签
        hovermode='x',
        hoverlabel=dict(
            bgcolor=APPLE_COLORS['white'],
            bordercolor=APPLE_COLORS['gray_200'],
            font=dict(
                family="Plus Jakarta Sans, -apple-system, sans-serif",
                size=13,
                color=APPLE_COLORS['dark'],
            ),
        ),
    )


def get_apple_line_colors() -> List[str]:
    """获取 Apple 风格的图表线条颜色序列"""
    return [
        '#0071E3',  # Apple Blue
        '#30D158',  # Apple Green
        '#FF9500',  # Apple Orange
        '#BF5AF2',  # Apple Purple
        '#FF453A',  # Apple Red
        '#64D2FF',  # Apple Teal
        '#5E5CE6',  # Apple Indigo
        '#FFD60A',  # Apple Yellow
        '#AC8E68',  # Apple Brown
        '#FF2D55',  # Apple Pink
    ]


def apply_apple_theme_to_figure(fig: go.Figure, **kwargs) -> go.Figure:
    """将 Apple 主题应用到现有的 Plotly 图表"""
    layout = get_apple_chart_layout(**kwargs)
    fig.update_layout(**layout)
    
    # 更新线条样式
    colors = get_apple_line_colors()
    for i, trace in enumerate(fig.data):
        if hasattr(trace, 'line'):
            trace.line.color = colors[i % len(colors)]
            trace.line.width = 2.5
        if hasattr(trace, 'marker'):
            trace.marker.color = colors[i % len(colors)]
    
    return fig


# ==================== Hero Section ====================
def render_hero_section(
    title: str = "Quant-AI Dashboard",
    subtitle: str = "AI-driven portfolio analytics and signal exploration",
    eyebrow: str = "QUANTITATIVE ANALYSIS",
    show_scroll_indicator: bool = True,
):
    """渲染 Apple 风格的 Hero Section（首屏）"""
    st.markdown(f"""
    <div class="hero-section">
        <div class="hero-content">
            <span class="hero-eyebrow">{eyebrow}</span>
            <h1 class="hero-title">{title}</h1>
            <p class="hero-subtitle">{subtitle}</p>
        </div>
        {"<div class='scroll-indicator'><span></span></div>" if show_scroll_indicator else ""}
    </div>
    
    <style>
    .scroll-indicator {{
        position: absolute;
        bottom: 40px;
        left: 50%;
        transform: translateX(-50%);
        animation: bounce 2s infinite;
    }}
    
    .scroll-indicator span {{
        display: block;
        width: 24px;
        height: 24px;
        border-right: 2px solid rgba(0,0,0,0.3);
        border-bottom: 2px solid rgba(0,0,0,0.3);
        transform: rotate(45deg);
    }}
    
    @keyframes bounce {{
        0%, 20%, 50%, 80%, 100% {{ transform: translateX(-50%) translateY(0); }}
        40% {{ transform: translateX(-50%) translateY(-10px); }}
        60% {{ transform: translateX(-50%) translateY(-5px); }}
    }}
    </style>
    """, unsafe_allow_html=True)


# ==================== Compact Header ====================
def render_compact_header(
    title: str = "Quant-AI Dashboard",
    subtitle: str = "AI-driven portfolio analytics",
):
    """渲染紧凑版标题（非首屏使用）"""
    st.markdown(f"""
    <div style="
        text-align: center;
        padding: 3rem 0 2rem 0;
        margin-bottom: 1rem;
    ">
        <h1 style="
            font-size: clamp(2.5rem, 5vw, 3.5rem);
            font-weight: 700;
            letter-spacing: -0.04em;
            line-height: 1.1;
            margin-bottom: 0.75rem;
            background: linear-gradient(135deg, #1D1D1F 0%, #48484A 50%, #1D1D1F 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        ">{title}</h1>
        <p style="
            font-size: 1.125rem;
            color: #8E8E93;
            font-weight: 400;
            letter-spacing: -0.01em;
            margin: 0;
        ">{subtitle}</p>
    </div>
    """, unsafe_allow_html=True)


# ==================== Bento Grid ====================
def render_bento_grid_start():
    """开始 Bento Grid 布局"""
    st.markdown('<div class="bento-grid">', unsafe_allow_html=True)


def render_bento_grid_end():
    """结束 Bento Grid 布局"""
    st.markdown('</div>', unsafe_allow_html=True)


def render_bento_card(
    content: str,
    size: str = "md",  # sm, md, lg, full
    tall: bool = False,
    icon: str = "",
    title: str = "",
    description: str = "",
):
    """渲染单个 Bento Card"""
    size_class = f"bento-{size}"
    tall_class = "bento-tall" if tall else ""
    
    st.markdown(f"""
    <div class="bento-card {size_class} {tall_class}">
        {f'<div class="feature-icon">{icon}</div>' if icon else ''}
        {f'<h4 class="feature-title">{title}</h4>' if title else ''}
        {f'<p class="feature-description">{description}</p>' if description else ''}
        {content}
    </div>
    """, unsafe_allow_html=True)


# ==================== Feature Cards ====================
def render_feature_cards(features: List[Dict[str, str]]):
    """渲染特性卡片网格"""
    cols = st.columns(len(features))
    for i, feature in enumerate(features):
        with cols[i]:
            st.markdown(f"""
            <div class="feature-card">
                <div class="feature-icon">{feature.get('icon', '📊')}</div>
                <div class="feature-title">{feature.get('title', '')}</div>
                <div class="feature-description">{feature.get('description', '')}</div>
            </div>
            """, unsafe_allow_html=True)


# ==================== Stats Display ====================
def render_stats_row(stats: List[Dict[str, Any]]):
    """渲染统计数字行"""
    cols = st.columns(len(stats))
    for i, stat in enumerate(stats):
        with cols[i]:
            st.markdown(f"""
            <div style="text-align: center; padding: 2rem;">
                <div class="stat-number">{stat.get('value', '0')}</div>
                <div class="stat-label">{stat.get('label', '')}</div>
            </div>
            """, unsafe_allow_html=True)


# ==================== Section Divider ====================
def render_section_divider():
    """渲染 Apple 风格的分隔线"""
    st.markdown("""
    <div style="
        width: 100%;
        height: 1px;
        background: linear-gradient(90deg, 
            transparent 0%, 
            rgba(0,0,0,0.08) 20%, 
            rgba(0,0,0,0.08) 80%, 
            transparent 100%
        );
        margin: 4rem 0;
    "></div>
    """, unsafe_allow_html=True)


# ==================== Section Header ====================
def render_section_header(
    title: str,
    subtitle: str = "",
    align: str = "left",  # left, center
):
    """渲染章节标题"""
    text_align = "center" if align == "center" else "left"
    margin = "0 auto" if align == "center" else "0"
    
    st.markdown(f"""
    <div style="
        text-align: {text_align};
        margin: {margin};
        max-width: 800px;
        padding: 2rem 0;
    ">
        <h2 style="
            font-size: clamp(2rem, 4vw, 3rem);
            font-weight: 600;
            letter-spacing: -0.03em;
            line-height: 1.15;
            color: #1D1D1F;
            margin-bottom: 1rem;
        ">{title}</h2>
        {f'''<p style="
            font-size: 1.25rem;
            color: #8E8E93;
            line-height: 1.6;
            letter-spacing: -0.01em;
        ">{subtitle}</p>''' if subtitle else ''}
    </div>
    """, unsafe_allow_html=True)


# ==================== Glass Card ====================
def render_glass_card(content: str, padding: str = "2rem"):
    """渲染毛玻璃效果卡片"""
    st.markdown(f"""
    <div class="glass-card" style="padding: {padding};">
        {content}
    </div>
    """, unsafe_allow_html=True)


# ==================== Scrollytelling Effects ====================
def inject_scrollytelling_js():
    """注入滚动叙事效果的 JavaScript"""
    st.markdown("""
    <script>
    // 等待 DOM 加载完成
    document.addEventListener('DOMContentLoaded', function() {
        // 淡入效果观察器
        const fadeObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');
                }
            });
        }, {
            threshold: 0.1,
            rootMargin: '0px 0px -50px 0px'
        });
        
        // 观察所有需要淡入的元素
        document.querySelectorAll('.fade-up').forEach(el => {
            fadeObserver.observe(el);
        });
        
        // 视差滚动效果
        window.addEventListener('scroll', function() {
            const scrolled = window.pageYOffset;
            
            document.querySelectorAll('.parallax-bg').forEach(bg => {
                const speed = 0.5;
                bg.style.transform = `translateY(${scrolled * speed}px)`;
            });
        });
    });
    </script>
    """, unsafe_allow_html=True)


# ==================== 动画延迟包装器 ====================
def with_fade_in(content: str, delay: int = 0) -> str:
    """为内容添加淡入动画效果"""
    delay_class = f"delay-{delay}" if delay > 0 else ""
    return f'<div class="fade-up {delay_class}">{content}</div>'


# ==================== Premium Badge ====================
def render_premium_badge(text: str = "Pro"):
    """渲染高级徽章"""
    st.markdown(f"""
    <span style="
        display: inline-flex;
        align-items: center;
        padding: 0.25rem 0.75rem;
        background: linear-gradient(135deg, #0071E3 0%, #409CFF 100%);
        color: white;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        border-radius: 20px;
        margin-left: 0.5rem;
    ">{text}</span>
    """, unsafe_allow_html=True)


# ==================== Loading Skeleton ====================
def render_skeleton(height: str = "200px", width: str = "100%"):
    """渲染加载骨架屏"""
    st.markdown(f"""
    <div style="
        height: {height};
        width: {width};
        background: linear-gradient(90deg, 
            #F2F2F7 0%, 
            #E5E5EA 50%, 
            #F2F2F7 100%
        );
        background-size: 200% 100%;
        animation: shimmer 1.5s infinite;
        border-radius: 16px;
    "></div>
    
    <style>
    @keyframes shimmer {{
        0% {{ background-position: 200% 0; }}
        100% {{ background-position: -200% 0; }}
    }}
    </style>
    """, unsafe_allow_html=True)


# ==================== Gradient Text ====================
def render_gradient_text(
    text: str,
    size: str = "3rem",
    gradient: str = "linear-gradient(135deg, #0071E3 0%, #BF5AF2 100%)",
):
    """渲染渐变文字"""
    st.markdown(f"""
    <span style="
        font-size: {size};
        font-weight: 700;
        letter-spacing: -0.03em;
        background: {gradient};
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    ">{text}</span>
    """, unsafe_allow_html=True)


# ==================== 数据可视化辅助 ====================
def create_apple_line_chart(
    data,
    x_col: str,
    y_cols: List[str],
    names: Optional[Dict[str, str]] = None,
    title: str = "",
    xaxis_title: str = "",
    yaxis_title: str = "",
    height: int = 400,
) -> go.Figure:
    """创建 Apple 风格的折线图"""
    fig = go.Figure()
    colors = get_apple_line_colors()
    names = names or {}
    
    for i, col in enumerate(y_cols):
        fig.add_trace(go.Scatter(
            x=data[x_col] if x_col else data.index,
            y=data[col],
            mode='lines',
            name=names.get(col, col),
            line=dict(
                color=colors[i % len(colors)],
                width=2.5,
            ),
            hovertemplate='%{y:.2f}<extra></extra>',
        ))
    
    fig.update_layout(**get_apple_chart_layout(
        title=title,
        height=height,
        xaxis_title=xaxis_title,
        yaxis_title=yaxis_title,
    ))
    
    return fig


def create_apple_bar_chart(
    data,
    x_col: str,
    y_col: str,
    title: str = "",
    xaxis_title: str = "",
    yaxis_title: str = "",
    height: int = 400,
    color: str = None,
) -> go.Figure:
    """创建 Apple 风格的柱状图"""
    fig = go.Figure(data=[
        go.Bar(
            x=data[x_col] if x_col else data.index,
            y=data[y_col],
            marker_color=color or APPLE_COLORS['blue'],
            marker_line_width=0,
            hovertemplate='%{y:.2f}<extra></extra>',
        )
    ])
    
    fig.update_layout(**get_apple_chart_layout(
        title=title,
        height=height,
        show_legend=False,
        xaxis_title=xaxis_title,
        yaxis_title=yaxis_title,
    ))
    
    return fig


def create_apple_heatmap(
    data,
    title: str = "",
    height: int = 400,
    colorscale: str = "RdBu",
) -> go.Figure:
    """创建 Apple 风格的热力图"""
    z = data.values
    text = [[f"{val:.2f}" for val in row] for row in z]
    
    fig = go.Figure(data=go.Heatmap(
        z=z,
        x=list(data.columns),
        y=list(data.index),
        colorscale=colorscale,
        zmin=-1,
        zmax=1,
        zmid=0,
        text=text,
        texttemplate="%{text}",
        textfont=dict(size=11),
        colorbar=dict(
            title="",
            thickness=15,
            len=0.6,
            tickfont=dict(size=11, color=APPLE_COLORS['gray_600']),
        ),
        hovertemplate='%{x} × %{y}: %{z:.2f}<extra></extra>',
    ))
    
    fig.update_layout(**get_apple_chart_layout(
        title=title,
        height=height,
        show_legend=False,
    ))
    
    return fig


def create_apple_pie_chart(
    labels: List[str],
    values: List[float],
    title: str = "",
    height: int = 400,
) -> go.Figure:
    """创建 Apple 风格的饼图"""
    colors = get_apple_line_colors()
    
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.55,
        marker=dict(
            colors=colors[:len(labels)],
            line=dict(color=APPLE_COLORS['white'], width=2),
        ),
        textinfo='percent',
        textfont=dict(size=13, color=APPLE_COLORS['dark']),
        hovertemplate='%{label}: %{percent}<extra></extra>',
    )])
    
    fig.update_layout(**get_apple_chart_layout(
        title=title,
        height=height,
        show_legend=True,
    ))
    
    return fig

