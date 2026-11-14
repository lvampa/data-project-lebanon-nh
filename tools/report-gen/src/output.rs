use anyhow::Result;
use serde::Serialize;
use std::io::ErrorKind;
use std::path::Path;

pub fn write_json<T: Serialize>(dir: &Path, filename: &str, data: &T) -> Result<()> {
    std::fs::create_dir_all(dir)?;
    let path = dir.join(filename);
    let json = serde_json::to_string_pretty(data)?;
    std::fs::write(path, json)?;
    Ok(())
}

/// Deletes the named files from `dir`, so a run that fails halfway cannot leave an old
/// export to be deployed. Only those files go; anything else in the folder stays, and a
/// file that is already missing is fine.
pub fn clear_files(dir: &Path, names: &[&str]) -> Result<()> {
    for name in names {
        match std::fs::remove_file(dir.join(name)) {
            Ok(()) => {}
            Err(error) if error.kind() == ErrorKind::NotFound => {}
            Err(error) => return Err(error.into()),
        }
    }
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
    fn clear_files_deletes_only_the_named_files() {
        let dir = tempdir().unwrap();
        for name in ["incidents.json", "stats.json", "notes.txt", "old.json"] {
            std::fs::write(dir.path().join(name), "x").unwrap();
        }

        clear_files(dir.path(), &["incidents.json", "stats.json"]).unwrap();

        assert!(!dir.path().join("incidents.json").exists());
        assert!(!dir.path().join("stats.json").exists());
        assert!(dir.path().join("notes.txt").exists());
        assert!(dir.path().join("old.json").exists());
    }

    #[test]
    fn clear_files_ignores_missing_files_and_a_missing_directory() {
        let dir = tempdir().unwrap();

        clear_files(dir.path(), &["incidents.json"]).unwrap();
        clear_files(&dir.path().join("nope"), &["incidents.json"]).unwrap();
    }
}
