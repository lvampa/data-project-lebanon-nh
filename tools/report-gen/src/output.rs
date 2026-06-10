use anyhow::Result;
use serde::Serialize;
use std::path::Path;

pub fn write_json<T: Serialize>(dir: &Path, filename: &str, data: &T) -> Result<()> {
    std::fs::create_dir_all(dir)?;
    let path = dir.join(filename);
    let json = serde_json::to_string_pretty(data)?;
    std::fs::write(path, json)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    use tempfile::tempdir;

    #[test]
    fn write_json_creates_file_with_correct_content() {
        let dir = tempdir().unwrap();
        let data = json!({"key": "value", "count": 42});
        write_json(dir.path(), "test.json", &data).unwrap();
        let content = std::fs::read_to_string(dir.path().join("test.json")).unwrap();
        let parsed: serde_json::Value = serde_json::from_str(&content).unwrap();
        assert_eq!(parsed["key"], "value");
        assert_eq!(parsed["count"], 42);
    }

    #[test]
    fn write_json_creates_output_dir_if_missing() {
        let dir = tempdir().unwrap();
        let nested = dir.path().join("a").join("b");
        let data = json!({"x": 1});
        write_json(&nested, "out.json", &data).unwrap();
        assert!(nested.join("out.json").exists());
    }
}
