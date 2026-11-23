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

/// For a file the browser downloads whole, where indenting would be most of its size.
pub fn write_json_compact<T: Serialize>(dir: &Path, filename: &str, data: &T) -> Result<()> {
    std::fs::create_dir_all(dir)?;
    std::fs::write(dir.join(filename), serde_json::to_string(data)?)?;
    Ok(())
}

/// Empties a directory the exporter owns, so a file for a place that is gone is not left.
pub fn reset_dir(dir: &Path) -> Result<()> {
    if dir.exists() {
        std::fs::remove_dir_all(dir)?;
    }
    std::fs::create_dir_all(dir)?;
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

    #[test]
    fn write_json_compact_writes_one_line_with_no_spaces() {
        let dir = tempdir().unwrap();
        write_json_compact(dir.path(), "c.json", &json!({"a": [1, 2], "b": "x"})).unwrap();
        let content = std::fs::read_to_string(dir.path().join("c.json")).unwrap();
        assert_eq!(content, r#"{"a":[1,2],"b":"x"}"#);
    }

    #[test]
    fn reset_dir_removes_old_files_and_keeps_the_directory() {
        let dir = tempdir().unwrap();
        let places = dir.path().join("places");
        write_json(&places, "old.json", &json!({"x": 1})).unwrap();

        reset_dir(&places).unwrap();

        assert!(places.is_dir());
        assert!(!places.join("old.json").exists());
    }
}
