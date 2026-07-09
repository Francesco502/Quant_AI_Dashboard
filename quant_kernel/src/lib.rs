use pyo3::prelude::*;
use pyo3::types::PyDict;

fn extract_vec(rows: &Bound<'_, PyDict>, key: &str, n: usize, default: f64) -> PyResult<Vec<f64>> {
    match rows.get_item(key)? {
        Some(value) => value.extract::<Vec<f64>>(),
        None => Ok(vec![default; n]),
    }
}

fn finite_or(value: f64, default: f64) -> f64 {
    if value.is_finite() {
        value
    } else {
        default
    }
}

#[pyfunction]
fn score_feature_rows(rows: &Bound<'_, PyDict>) -> PyResult<Vec<f64>> {
    let close = extract_vec(rows, "close", 0, 0.0)?;
    let n = close.len();
    if n == 0 {
        return Ok(Vec::new());
    }

    let ma20 = extract_vec(rows, "ma_20", n, f64::NAN)?;
    let ma60 = extract_vec(rows, "ma_60", n, f64::NAN)?;
    let ret20 = extract_vec(rows, "return_20d", n, 0.0)?;
    let rsi = extract_vec(rows, "rsi_14", n, 50.0)?;
    let vol = extract_vec(rows, "volatility_20d", n, 0.0)?;
    let volume_ratio = extract_vec(rows, "volume_ratio_20d", n, 1.0)?;

    let mut scores = Vec::with_capacity(n);
    for i in 0..n {
        let c = finite_or(close.get(i).copied().unwrap_or(0.0), 0.0);
        let m20 = ma20.get(i).copied().unwrap_or(f64::NAN);
        let m60 = ma60.get(i).copied().unwrap_or(f64::NAN);
        let trend = if m20.is_finite() && m60.is_finite() && m60 != 0.0 {
            (m20 / m60 - 1.0) * 100.0
        } else {
            0.0
        };
        let price_vs_ma = if m20.is_finite() && m20 != 0.0 {
            (c / m20 - 1.0) * 100.0
        } else {
            0.0
        };
        let momentum = finite_or(ret20.get(i).copied().unwrap_or(0.0), 0.0) * 100.0;
        let rsi_component = 50.0 - (finite_or(rsi.get(i).copied().unwrap_or(50.0), 50.0) - 55.0).abs();
        let volume_component = finite_or(volume_ratio.get(i).copied().unwrap_or(1.0), 1.0).clamp(0.0, 3.0) * 8.0;
        let volatility_penalty = finite_or(vol.get(i).copied().unwrap_or(0.0), 0.0) * 120.0;
        let raw = 50.0
            + momentum * 1.8
            + trend * 1.2
            + price_vs_ma * 0.5
            + rsi_component * 0.35
            + volume_component
            - volatility_penalty;
        scores.push(raw.clamp(0.0, 100.0));
    }
    Ok(scores)
}

#[pymodule]
fn quant_kernel(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(score_feature_rows, module)?)?;
    Ok(())
}
