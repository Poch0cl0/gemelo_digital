# Entrenamiento CRISP-DM del acompañante predictivo ABS–SD

Pipeline de aprendizaje automático sobre **CDC/NCHS NHAMCS 2022** (16.025 visitas de urgencias en EE. UU.). Los datos públicos se descargan a `datos/nhamcs/ed2022-stata.zip`. [Documentación oficial](https://www.cdc.gov/nchs/nhamcs/documentation/index.html).

## Metodología CRISP-DM implementada

| Fase | Módulo | Contenido |
|---|---|---|
| Comprensión del negocio | `train_ml.py` → `business` | Objetivo exploratorio; no sustituye el simulador ABS–SD |
| Comprensión de datos (EDA) | `motor/eda.py` | Descriptivos ponderados, histogramas, correlación Spearman, LOV/espera por triaje, pruebas KS entre particiones |
| Preparación | `motor/ml.py` | Limpieza de 11 variables de llegada; imputación mediana en modelos lineales |
| Modelado | `motor/ml_models.py` | 5 candidatos: referencia, lineal, árbol, Random Forest, HistGradientBoosting |
| Validación cruzada | `motor/train_ml.py` | CV anidada por hospital (`GroupKFold` 5×3); `StratifiedGroupKFold` para ingreso |
| Hiperparámetros | `RandomizedSearchCV` | Búsqueda aleatoria con CV interna por hospital y pesos PATWT |
| Selección | Bootstrap OOF por hospital + Holm | Mejor métrica fuera de pliegue; parsimonia si un modelo más simple no es significativamente peor (Nadeau–Bengio como prueba complementaria) |
| Pruebas estadísticas | `motor/ml_stats.py` | Bootstrap por hospital (B=2000), Wilcoxon, DeLong, Friedman/Nemenyi, Hosmer–Lemeshow, calibración |
| Explicabilidad | `motor/ml_explain.py` | Permutación, SHAP global/local, PDP, ROC/PR, residuos |
| Despliegue | `/ml`, `/api/ml/report`, `/api/ml/predict` | Interfaz SVG con interpretación bajo cada gráfico/tabla |

## Partición de datos

- **80 % trainval** / **20 % prueba**, sin hospitales compartidos (`GroupShuffleSplit`, semilla fija).
- La prueba (≈38 hospitales) no interviene en ajuste ni selección de hiperparámetros.
- Pesos de encuesta **PATWT** en entrenamiento, selección y métricas.

## Objetivos

| Clave | Columna NHAMCS | Tipo |
|---|---|---|
| `visit_minutes` | LOV | Regresión (estancia total, incluye espera) |
| `wait_minutes` | WAITTIME | Regresión (espera hasta atención) |
| `hospitalization` | ADMITHOS | Clasificación (ingreso en el mismo hospital) |

## Resultado medido (último entrenamiento)

| Objetivo | Modelo seleccionado | Prueba | Referencia |
|---|---|---:|---:|
| Estancia LOV | HistGradientBoosting | MAE 153,4 min | MAE 164,4 min |
| Espera WAITTIME | HistGradientBoosting | MAE 29,4 min | MAE 27,6 min |
| Ingreso ADMITHOS | Regresión logística (parsimonia frente a Random Forest) | Brier 0,0695 · AUC 0,818 | Brier 0,0823 |

Estancia: mejora de −11,0 min (IC 95 % bootstrap por hospital −15,4 a −7,2; p < 0,001). Ingreso: Brier −0,0128 (IC −0,023 a −0,005; p < 0,001). Espera: aunque en validación cruzada superó a la referencia, en los hospitales de prueba la diferencia es +1,8 min (IC −0,4 a +4,3; p = 0,26), es decir, no concluyente. Resultados en modo rápido (3 pliegues, B = 200); `python -m motor.train_ml` usa 5 pliegues y B = 2000.

## Uso

```powershell
python -m pip install -r requirements-ml.txt
python -m motor.train_ml          # entrenamiento completo (~30–60 min)
python -m motor.train_ml --quick  # modo rápido para pruebas (~10 min)
python -m motor.ui
```

- **Simulador:** sección ML en `/simulator` con predicción individual y explicación SHAP local.
- **Laboratorio CRISP-DM:** `http://127.0.0.1:8765/ml` con pestañas por fase.
- **Asistente LangGraph:** `http://127.0.0.1:8765/asistente` (preguntas en lenguaje natural sobre el informe).
- **API:** `GET /api/ml/status`, `GET /api/ml/report`, `POST /api/ml/predict`, `GET /api/agent/status`, `POST /api/agent/chat`.

### Asistente LangGraph (Gemini, Ollama o DeepSeek)

```powershell
python -m pip install -r requirements-agent.txt
python -m motor.ui
```

**Opción A — Gemini API (recomendado):**

Copia `.env.example` a `.env` y pon tu clave (el archivo `.env` no se sube a git):

```powershell
copy .env.example .env
# Edita .env: GEMINI_API_KEY=...  (https://aistudio.google.com/apikey)
python -m motor.demo_agent --gemini
```

**Opción B — Ollama local:**

```powershell
ollama pull qwen2.5:7b
set AGENT_PROVIDER=ollama
```

**Opción C — DeepSeek API:**

```powershell
# Edita .env: DEEPSEEK_API_KEY=sk-...
python -m motor.demo_agent --deepseek
```

**Demo sin API (simulación del grafo ReAct):**

```powershell
python -m motor.demo_agent --mock
```

Variables: `AGENT_PROVIDER` (`gemini` | `deepseek` | `ollama` | `mock`), `GEMINI_API_KEY`, `GEMINI_MODEL` (por defecto `gemini-2.0-flash`), `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL`, `OLLAMA_MODEL`, `OLLAMA_HOST`.
Si existe `GEMINI_API_KEY` sin `AGENT_PROVIDER`, se usa Gemini automáticamente.
El asistente consulta fragmentos de `informe.json` mediante herramientas; no carga el archivo completo (1,7 MB) en el contexto del modelo.

Ejemplo de predicción: `{"age":40,"triage":3}` (variables en `motor/ml.py`; `null` = ausente).

## Artefactos

En `resultados_ml/`:

| Archivo | Descripción |
|---|---|
| `modelos.joblib` | Modelos finales + muestra de fondo SHAP |
| `informe.json` | Informe v2 (EDA, CV, estadística, explicabilidad) |
| `predicciones_prueba.csv` | Predicciones en hospitales de prueba |

Solo se carga el artefacto cuyo SHA-256 coincide con `informe.json`.

## Pruebas

```powershell
python -m unittest discover -s motor -v
```

Incluye `test_ml_stats.py`, `test_eda.py` y `test_ml.py` (los dos últimos requieren artefactos entrenados).

## Limitaciones

- Datos estadounidenses 2022; sin validación en Perú ni víctimas masivas.
- LOV **no equivale** al trabajo basal `service` del simulador.
- Triaje NHAMCS 1–5 **no se convierte** a P0–P2.
- Bootstrap por hospital **aproxima** incertidumbre; no modela diseño complejo de encuesta (CSTRATM/CPSUM).
- Uso **experimental**; no para decisiones clínicas.

Los resultados del artículo en `resultados/` se conservan; este pipeline no los revalida.
