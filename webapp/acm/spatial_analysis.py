"""
spatial_analysis.py — Módulo reutilizable para análisis espacial de propiedades
Integración Django: views.py lo importa y llama a generar_grafico_espacial()
"""
import io
import os

# PRIMERO silenciar matplotlib ANTES de cualquier import
os.environ['MPLBACKEND'] = 'Agg'
os.environ['MATPLOTLIB_LOG_LEVEL'] = 'CRITICAL'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

import logging
logging.getLogger('matplotlib').setLevel(logging.CRITICAL)
logging.getLogger('matplotlib.font_manager').setLevel(logging.CRITICAL)
logging.getLogger('PIL').setLevel(logging.CRITICAL)

import matplotlib
matplotlib.use('Agg')
matplotlib.set_loglevel('critical')
# Usar cache de fuentes ya existente para no escanear todas las fuentes
import matplotlib.pyplot as plt
import numpy as np
import matplotlib.cm as cm
import matplotlib.patheffects as pe
from matplotlib.patches import Circle
from matplotlib.gridspec import GridSpec
from scipy.spatial.distance import cdist


# ── Paleta idéntica al gráfico original ──
BG      = '#0d1117'
PANEL   = '#0f2744'   # azul oscuro del mapa
PANEL2  = '#0a1628'   # paneles derecha
GRID_C  = '#ffffff'
WHITE   = '#e6edf3'
GOLD    = '#f0b429'
RED_H   = '#e94560'   # encabezado tabla


def _fig_to_png(fig, dpi=130):
    """Convierte una figura matplotlib a bytes PNG."""
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=dpi, bbox_inches='tight', facecolor=BG)
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def generar_mapa_espacial(propiedades: list[dict], dpi=130) -> bytes:
    """Genera solo el mapa espacial de burbujas. Reemplaza Google Maps."""
    df = _preparar(propiedades)
    fig, ax = plt.subplots(1, 1, figsize=(10, 8), facecolor=BG)
    ax.set_title('Mapa Espacial de Propiedades – Arequipa\n(Tamaño = Área Terreno  |  Color = Precio)',
                 fontsize=12, fontweight='bold', color=WHITE, pad=15)
    _dibujar_mapa(ax, df)
    fig.tight_layout(pad=2)
    return _fig_to_png(fig, dpi)


def generar_chart_precio(propiedades: list[dict], dpi=130) -> bytes:
    """Genera el scatter de Precio vs Distancia a Zona Premium."""
    df = _preparar(propiedades)
    fig, ax = plt.subplots(1, 1, figsize=(6, 3.5), facecolor=BG)
    _dibujar_scatter_precio(ax, df)
    fig.tight_layout(pad=1.5)
    return _fig_to_png(fig, dpi)


def generar_chart_pm2(propiedades: list[dict], dpi=130) -> bytes:
    """Genera el scatter de Precio/m² vs Distancia."""
    df = _preparar(propiedades)
    fig, ax = plt.subplots(1, 1, figsize=(6, 3.5), facecolor=BG)
    _dibujar_scatter_pm2(ax, df)
    fig.tight_layout(pad=1.5)
    return _fig_to_png(fig, dpi)


def generar_tabla_resumen(propiedades: list[dict], dpi=130) -> bytes:
    """Genera la tabla resumen de propiedades."""
    df = _preparar(propiedades)
    fig, ax = plt.subplots(1, 1, figsize=(6, 4), facecolor=BG)
    _dibujar_tabla(ax, df)
    fig.tight_layout(pad=1.5)
    return _fig_to_png(fig, dpi)


def generar_todo_json(propiedades: list[dict], dpi=130) -> dict:
    """
    Genera las 4 imágenes y devuelve dict con base64 de cada una.
    """
    import base64
    return {
        'mapa': base64.b64encode(generar_mapa_espacial(propiedades, dpi)).decode(),
        'chart_precio': base64.b64encode(generar_chart_precio(propiedades, dpi)).decode(),
        'chart_pm2': base64.b64encode(generar_chart_pm2(propiedades, dpi)).decode(),
        'tabla': base64.b64encode(generar_tabla_resumen(propiedades, dpi)).decode(),
    }


# Mantener compatibilidad con código existente
generar_grafico_espacial = generar_mapa_espacial


# ───────────────────────── helpers internos ─────────────────────────

def _preparar(propiedades):
    import pandas as pd
    df = pd.DataFrame(propiedades)

    lat_c = df['lat'].mean()
    lon_c = df['lon'].mean()
    df['x_m'] = (df['lon'] - lon_c) * 111000 * np.cos(np.radians(lat_c))
    df['y_m']  = (df['lat'] - lat_c) * 111000

    # Zona premium = centroide de propiedades >= percentil 60 de precio
    umbral = df['precio'].quantile(0.60)
    exp = df[df['precio'] >= umbral]
    cx, cy = exp['x_m'].mean(), exp['y_m'].mean()
    df['dist_premium'] = np.sqrt((df['x_m'] - cx)**2 + (df['y_m'] - cy)**2)

    df['_cx'] = cx
    df['_cy'] = cy

    norm = (df['precio'] - df['precio'].min()) / (df['precio'].max() - df['precio'].min() + 1)
    df['_norm_precio'] = norm
    return df


def _colores(df):
    return [cm.RdYlGn(p) for p in df['_norm_precio']]


def _dibujar_mapa(ax, df):
    ax.set_facecolor(PANEL)

    # Grilla suave
    for v in np.arange(-4000, 4500, 500):
        ax.axvline(v, color=WHITE, alpha=0.04, lw=0.5)
        ax.axhline(v, color=WHITE, alpha=0.04, lw=0.5)

    # Conexiones vecino más cercano
    coords = df[['x_m', 'y_m']].values
    dist_m = cdist(coords, coords)
    drawn  = set()
    for i in range(len(df)):
        d = dist_m[i].copy(); d[i] = np.inf
        j = int(np.argmin(d))
        pair = tuple(sorted([i, j]))
        if pair in drawn:
            continue
        ax.plot([df.iloc[i]['x_m'], df.iloc[j]['x_m']],
                [df.iloc[i]['y_m'], df.iloc[j]['y_m']],
                color=WHITE, alpha=0.18, lw=1, linestyle='--')
        mx = (df.iloc[i]['x_m'] + df.iloc[j]['x_m']) / 2
        my = (df.iloc[i]['y_m'] + df.iloc[j]['y_m']) / 2
        ax.text(mx, my, f"{dist_m[i,j]:.0f}m",
                color=WHITE, fontsize=6, ha='center', va='center', alpha=0.55)
        drawn.add(pair)

    # Círculo zona premium
    cx, cy = df['_cx'].iloc[0], df['_cy'].iloc[0]
    circ = Circle((cx, cy), 800, fill=True,
                  facecolor='gold', alpha=0.07,
                  edgecolor='gold', lw=1.8, linestyle='--')
    ax.add_patch(circ)
    ax.text(cx, cy - 950, '◆ Zona Premium',
            color=GOLD, fontsize=8.5, ha='center', fontweight='bold', alpha=0.85)

    # Burbujas
    sizes  = 180 + (df['area_terreno'] / df['area_terreno'].max()) * 620
    colors = _colores(df)
    ax.scatter(df['x_m'], df['y_m'],
               s=sizes, c=[df['_norm_precio'].iloc[i] for i in range(len(df))],
               cmap='RdYlGn', vmin=0, vmax=1,
               edgecolors=WHITE, linewidths=1.4, alpha=0.95, zorder=5)

    # Colorbar
    sm = cm.ScalarMappable(cmap='RdYlGn',
                           norm=plt.Normalize(df['precio'].min(), df['precio'].max()))
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, fraction=0.025, pad=0.01)
    cbar.set_label('Precio USD', color=WHITE, fontsize=8)
    cbar.ax.yaxis.set_tick_params(color=WHITE)
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color=WHITE, fontsize=7)

    # Etiquetas sobre cada burbuja
    for i, row in df.iterrows():
        ax.text(row['x_m'], row['y_m'],
                str(i + 1 if isinstance(i, int) else list(df.index).index(i) + 1),
                ha='center', va='center', fontsize=7,
                color='black', fontweight='bold', zorder=7)
        ax.annotate(
            f"${row['precio']//1000}K\n{row['area_terreno']:.0f}m²",
            (row['x_m'], row['y_m']),
            textcoords="offset points", xytext=(13, 5),
            fontsize=7.5, color=WHITE, fontweight='bold',
            path_effects=[pe.withStroke(linewidth=2, foreground='black')]
        )

    ax.set_xlabel('Distancia Este-Oeste (metros)', color=WHITE, fontsize=9)
    ax.set_ylabel('Distancia Norte-Sur (metros)',  color=WHITE, fontsize=9)
    ax.tick_params(colors=WHITE, labelsize=8)
    for s in ax.spines.values(): s.set_edgecolor('#1a3a5c')


def _dibujar_scatter_precio(ax, df):
    ax.set_facecolor(PANEL2)
    colors = _colores(df)
    ax.scatter(df['dist_premium'], df['precio'] / 1000,
               c=colors, s=75, edgecolors=WHITE, lw=0.7, zorder=3)

    z = np.polyfit(df['dist_premium'], df['precio'] / 1000, 1)
    xr = np.linspace(df['dist_premium'].min(), df['dist_premium'].max(), 100)
    ax.plot(xr, np.poly1d(z)(xr), WHITE, lw=1.4, alpha=0.5, linestyle='--')

    for _, row in df.iterrows():
        ax.annotate(f"${row['precio']//1000}K",
                    (row['dist_premium'], row['precio']/1000),
                    textcoords="offset points", xytext=(4, 2),
                    fontsize=6.5, color=WHITE, alpha=0.85)

    r2 = np.corrcoef(df['dist_premium'], df['precio'])[0, 1]
    ax.set_title(f'Precio vs Cercanía a Zona Premium\nR² correlación: {r2:.2f}',
                 color=WHITE, fontsize=8.5, fontweight='bold')
    ax.set_xlabel('Distancia a Zona Premium (m)', color=WHITE, fontsize=8)
    ax.set_ylabel('Precio (USD miles)',            color=WHITE, fontsize=8)
    _estilo_ax(ax)


def _dibujar_scatter_pm2(ax, df):
    ax.set_facecolor(PANEL2)
    colors = _colores(df)
    ax.scatter(df['dist_premium'], df['precio_m2_terreno'],
               c=colors, s=75, edgecolors=WHITE, lw=0.7, zorder=3)

    z = np.polyfit(df['dist_premium'], df['precio_m2_terreno'], 1)
    xr = np.linspace(df['dist_premium'].min(), df['dist_premium'].max(), 100)
    ax.plot(xr, np.poly1d(z)(xr), WHITE, lw=1.4, alpha=0.5, linestyle='--')

    for _, row in df.iterrows():
        ax.annotate(f"${row['precio_m2_terreno']:.0f}",
                    (row['dist_premium'], row['precio_m2_terreno']),
                    textcoords="offset points", xytext=(4, 2),
                    fontsize=6.5, color=WHITE, alpha=0.85)

    ax.set_title('Precio/m² vs Distancia\n(Efecto de ubicación sobre valor unitario)',
                 color=WHITE, fontsize=8.5, fontweight='bold')
    ax.set_xlabel('Distancia a Zona Premium (m)', color=WHITE, fontsize=8)
    ax.set_ylabel('USD/m² terreno',               color=WHITE, fontsize=8)
    _estilo_ax(ax)


def _dibujar_tabla(ax, df):
    ax.set_facecolor(PANEL2)
    ax.axis('off')

    filas = []
    for _, row in df.sort_values('precio', ascending=False).iterrows():
        filas.append([
            f"${row['precio']//1000}K",
            f"{row['area_terreno']:.0f}m²",
            f"${row['precio_m2_terreno']:.0f}",
            f"{row['dist_premium']:.0f}m",
            f"{row['antiguedad']:.0f}a",
        ])

    headers = ['Precio', 'Terreno', '$/m²', 'Dist.Prem', 'Antigüed']
    tbl = ax.table(cellText=filas, colLabels=headers,
                   loc='center', cellLoc='center')
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8)
    tbl.scale(1, 1.25)

    for (r, c), cell in tbl.get_celld().items():
        cell.set_edgecolor('#1a3a5c')
        if r == 0:
            cell.set_facecolor(RED_H)
            cell.set_text_props(color=WHITE, fontweight='bold')
        elif r % 2 == 0:
            cell.set_facecolor('#0f2744')
            cell.set_text_props(color=WHITE)
        else:
            cell.set_facecolor(PANEL2)
            cell.set_text_props(color='#aabbcc')

    ax.set_title('Resumen por Propiedad', color=WHITE, fontsize=8.5,
                 fontweight='bold', pad=10)


def _estilo_ax(ax):
    ax.tick_params(colors=WHITE, labelsize=7.5)
    ax.grid(True, alpha=0.12, color=WHITE)
    for s in ax.spines.values(): s.set_edgecolor('#1a3a5c')
