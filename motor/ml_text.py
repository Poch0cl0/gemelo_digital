"""Generate 'Cómo leerlo' and 'Interpretación' texts for ML report blocks."""

TARGET_LABELS = {
    'visit_minutes': 'estancia total (LOV)',
    'wait_minutes': 'espera hasta atención (WAITTIME)',
    'hospitalization': 'hospitalización en el mismo centro (ADMITHOS)',
}

MODEL_LABELS = {
    'baseline': 'referencia constante',
    'linear': 'modelo lineal regularizado',
    'decision_tree': 'árbol de decisión',
    'random_forest': 'bosque aleatorio',
    'hist_gradient_boosting': 'gradient boosting histogramático',
}


def eda_block_text(block, data, extra=None):
    if block == 'descriptives':
        max_miss = max(v['weighted']['missing'] for v in data.values())
        worst = max(data, key=lambda k: data[k]['weighted']['missing'])
        return {
            'como_leer': 'Tabla de estadísticos por variable de llegada: n, faltantes, media ponderada '
                         '(PATWT), mediana, rango intercuartílico y atípicos según IQR.',
            'interpretacion': f'La variable con mayor proporción de faltantes es {worst} '
                              f'({max_miss:.1%}). Las distribuciones guían la imputación mediana '
                              'y el tratamiento de ausencias en los modelos.',
        }
    if block == 'targets':
        parts = []
        if 'visit_minutes' in data:
            parts.append(f"LOV mediana {data['visit_minutes'].get('median', 0):.0f} min")
        if 'wait_minutes' in data:
            parts.append(f"espera mediana {data['wait_minutes'].get('median', 0):.0f} min")
        if 'hospitalization' in data:
            parts.append(f"prevalencia de ingreso {data['hospitalization'].get('prevalence', 0):.1%}")
        return {
            'como_leer': 'Distribución de los tres objetivos. LOV y WAITTIME tienen colas largas; '
                         'ADMITHOS es binario (prevalencia).',
            'interpretacion': 'Objetivos: ' + '; '.join(parts) + '. Las colas largas justifican MAE '
                              'y pérdida absoluta en regresión.',
        }
    if block == 'by_triage':
        sig = [k for k, p in (extra or {}).items() if p < 0.05]
        return {
            'como_leer': 'Mediana y cuartiles del objetivo por nivel de triaje NHAMCS (1–5). '
                         'Kruskal–Wallis prueba diferencias entre niveles.',
            'interpretacion': ('El triaje discrimina los objetivos (p<0,05 en ' + ', '.join(sig) + '). '
                               if sig else 'No se detectan diferencias globales significativas entre niveles de triaje. '),
        }
    if block == 'correlation':
        return {
            'como_leer': 'Correlación de Spearman entre variables y objetivos. Valores cercanos a ±1 '
                         'indican asociación monótona fuerte.',
            'interpretacion': 'La matriz orienta la selección de variables; correlaciones altas entre '
                              'presiones sistólica/diastólica sugieren redundancia parcial.',
        }
    if block == 'partitions':
        sig = [t['variable'] for t in data if t.get('holm_p', 1) < 0.05]
        return {
            'como_leer': 'Prueba de Kolmogorov–Smirnov entre particiones (entrenamiento, validación, prueba) '
                         'con corrección de Holm.',
            'interpretacion': ('Diferencias significativas en: ' + ', '.join(sig) + '. '
                             if sig else 'Las particiones por hospital muestran distribuciones similares en las variables revisadas. '),
        }
    return {'como_leer': '', 'interpretacion': ''}


def cv_text(target, cv_results, selected):
    label = TARGET_LABELS.get(target, target)
    best = cv_results.get(selected, {})
    return {
        'como_leer': f'Validación cruzada anidada por hospital (5 pliegues externos) para {label}. '
                     'Cada barra es la media ± desviación de la métrica por pliegue.',
        'interpretacion': f'Se seleccionó {MODEL_LABELS.get(selected, selected)} con media '
                          f'{best.get("mean", 0):.2f} ± {best.get("std", 0):.2f} en validación cruzada.',
    }


def test_text(target, test_result, stats_block):
    label = TARGET_LABELS.get(target, target)
    metric = 'Brier' if target == 'hospitalization' else 'MAE'
    sel = test_result.get('test_selected', {})
    key = 'brier' if target == 'hospitalization' else 'mae_minutes'
    ci = stats_block.get('metric_ci', {})
    return {
        'como_leer': f'Evaluación única en hospitales de prueba para {label}. {metric} menor es mejor.',
        'interpretacion': f'{metric} en prueba: {sel.get(key, 0):.2f}. '
                          f'IC 95% bootstrap por hospital: [{ci.get("ci_low", 0):.2f}, {ci.get("ci_high", 0):.2f}]. '
                          f'Wilcoxon/DeLong p={stats_block.get("comparison_p", "N/A")}.',
    }


def explain_text(feature, importance):
    return {
        'como_leer': f'Importancia global de {feature} por permutación y SHAP (|valor medio|).',
        'interpretacion': f'{feature} contribuye con importancia {importance:.3f} relativa al modelo final.',
    }


def local_explanation(contributions, prediction, target, unit='minutos'):
    label = TARGET_LABELS.get(target, target)
    top = sorted(contributions.items(), key=lambda kv: abs(kv[1]), reverse=True)[:3]
    classification = unit != 'minutos'
    parts = [f'{k} ({v:+.2f} {unit}, {"sube" if v > 0 else "baja"})' for k, v in top]
    value = f'{prediction:.1%}' if classification else f'{prediction:.0f} min'
    return (f'Para {label}, la predicción es {value}. '
            f'Las variables que más la mueven respecto al promedio son: {", ".join(parts)}.')
