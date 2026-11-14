use serde_json::Value;
use std::path::Path;

/// The public files a deploy needs, all of which must be present.
const PUBLIC_FILES: [&str; 4] = [
    "incidents.json",
    "addresses.json",
    "properties.json",
    "stats.json",
];

/// Fields that must be empty in each file, because they identify people.
const LEAK_FIELDS: [(&str, &[&str]); 2] = [
    ("incidents.json", &["officer", "reference_number"]),
    ("properties.json", &["owner", "owner_address"]),
];

/// Reads the written files and returns one line per problem; no lines means a clean export.
///
/// It checks the files and not the queries, so it catches a leak however it got in.
pub fn check_dir(dir: &Path) -> Vec<String> {
    let mut problems = Vec::new();
    for file in PUBLIC_FILES {
        let Some(rows) = read_json(dir, file, &mut problems) else {
            continue;
        };
        for (leaky_file, fields) in LEAK_FIELDS {
            if file == leaky_file {
                problems.extend(leaks_in(file, &rows, fields));
            }
        }
    }
    problems
}

fn read_json(dir: &Path, file: &str, problems: &mut Vec<String>) -> Option<Value> {
    let text = match std::fs::read_to_string(dir.join(file)) {
        Ok(text) => text,
        Err(error) => {
            problems.push(format!("{file} could not be read: {error}"));
            return None;
        }
    };
    match serde_json::from_str(&text) {
        Ok(value) => Some(value),
        Err(error) => {
            problems.push(format!("{file} is not valid JSON: {error}"));
            None
        }
    }
}

fn leaks_in(file: &str, rows: &Value, fields: &[&str]) -> Vec<String> {
    let Some(rows) = rows.as_array() else {
        return vec![format!("{file} is not a JSON array")];
    };
    fields
        .iter()
        .filter_map(|field| {
            let count = rows
                .iter()
                .filter(|row| row.get(field).is_some_and(is_filled))
                .count();
            (count > 0).then(|| format!("{file}: {count} rows have a non-empty {field}"))
        })
        .collect()
}

fn is_filled(value: &Value) -> bool {
    match value {
        Value::Null => false,
        Value::String(text) => !text.trim().is_empty(),
        _ => true,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    use tempfile::{TempDir, tempdir};

    fn write(dir: &TempDir, file: &str, content: &Value) {
        std::fs::write(dir.path().join(file), content.to_string()).unwrap();
    }

    fn clean_export() -> TempDir {
        let dir = tempdir().unwrap();
        write(
            &dir,
            "incidents.json",
            &json!([
                {"case_number": "26-1", "officer": null, "reference_number": null},
                {"case_number": "26-2", "officer": "", "reference_number": "  "},
            ]),
        );
        write(&dir, "addresses.json", &json!([]));
        write(
            &dir,
            "properties.json",
            &json!([{"parcel_id": "1", "owner": null, "owner_address": null}]),
        );
        write(&dir, "stats.json", &json!({"total": 2}));
        dir
    }

    #[test]
    fn a_clean_export_passes() {
        assert!(check_dir(clean_export().path()).is_empty());
    }

    #[test]
    fn each_leaked_field_fails_with_its_file_and_row_count() {
        let cases = [
            ("incidents.json", "officer"),
            ("incidents.json", "reference_number"),
            ("properties.json", "owner"),
            ("properties.json", "owner_address"),
        ];
        for (file, field) in cases {
            let dir = clean_export();
            write(
                &dir,
                file,
                &json!([{field: "Smith"}, {field: "Jones"}, {field: null}]),
            );

            assert_eq!(
                check_dir(dir.path()),
                vec![format!("{file}: 2 rows have a non-empty {field}")]
            );
        }
    }

    #[test]
    fn every_leaked_field_is_reported_in_one_run() {
        let dir = clean_export();
        write(
            &dir,
            "incidents.json",
            &json!([{"officer": "Smith", "reference_number": "R-1"}]),
        );
        write(
            &dir,
            "properties.json",
            &json!([{"owner": "Acme LLC", "owner_address": "1 Main St"}]),
        );

        assert_eq!(check_dir(dir.path()).len(), 4);
    }

    #[test]
    fn a_number_in_a_leak_field_counts_as_filled() {
        let dir = clean_export();
        write(&dir, "incidents.json", &json!([{"officer": 1234}]));

        assert_eq!(
            check_dir(dir.path()),
            vec!["incidents.json: 1 rows have a non-empty officer"]
        );
    }

    #[test]
    fn a_missing_public_file_fails() {
        for file in PUBLIC_FILES {
            let dir = clean_export();
            std::fs::remove_file(dir.path().join(file)).unwrap();

            let problems = check_dir(dir.path());

            assert_eq!(problems.len(), 1, "{file}");
            assert!(problems[0].starts_with(&format!("{file} could not be read")));
        }
    }

    #[test]
    fn a_missing_directory_fails_for_every_file() {
        let dir = tempdir().unwrap();

        assert_eq!(
            check_dir(&dir.path().join("nope")).len(),
            PUBLIC_FILES.len()
        );
    }

    #[test]
    fn a_file_that_is_not_json_fails() {
        let dir = clean_export();
        std::fs::write(dir.path().join("stats.json"), "{oops").unwrap();

        let problems = check_dir(dir.path());

        assert_eq!(problems.len(), 1);
        assert!(problems[0].starts_with("stats.json is not valid JSON"));
    }

    #[test]
    fn a_leak_file_that_is_not_an_array_fails() {
        let dir = clean_export();
        write(&dir, "incidents.json", &json!({"officer": "Smith"}));

        assert_eq!(
            check_dir(dir.path()),
            vec!["incidents.json is not a JSON array"]
        );
    }

    #[test]
    fn staff_is_not_checked() {
        let dir = clean_export();
        write(
            &dir,
            "staff.json",
            &json!([{"name": "Pat", "email": "pat@x"}]),
        );

        assert!(check_dir(dir.path()).is_empty());
    }
}
