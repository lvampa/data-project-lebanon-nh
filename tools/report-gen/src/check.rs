use serde_json::Value;
use std::path::Path;

/// The public files a deploy needs, all of which must be present.
const PUBLIC_FILES: [&str; 4] = [
    "incidents.json",
    "addresses.json",
    "properties.json",
    "stats.json",
];

/// What a field must not hold, in one file: the rows whose `fields` fail `is_bad`.
struct Rule {
    file: &'static str,
    fields: &'static [&'static str],
    is_bad: fn(&Value) -> bool,
    /// Finishes "N rows have ..." before the field name.
    what: &'static str,
}

const RULES: [Rule; 4] = [
    // Fields that identify people stay empty.
    Rule {
        file: "incidents.json",
        fields: &["officer", "reference_number"],
        is_bad: is_filled,
        what: "a non-empty",
    },
    Rule {
        file: "properties.json",
        fields: &["owner", "owner_address"],
        is_bad: is_filled,
        what: "a non-empty",
    },
    // Public locations carry no number that could name a home.
    Rule {
        file: "incidents.json",
        fields: &["location"],
        is_bad: has_unexplained_number,
        what: "an unexpected number in",
    },
    Rule {
        file: "addresses.json",
        fields: &["raw_address", "normalized_address"],
        is_bad: has_unexplained_number,
        what: "an unexpected number in",
    },
];

/// Reads the written files and returns one line per problem; no lines means a clean export.
///
/// It checks the files and not the queries, so it catches a leak however it got in.
/// A field that is absent from a row is not a leak, so it passes.
pub fn check_dir(dir: &Path) -> Vec<String> {
    let mut problems = Vec::new();
    for file in PUBLIC_FILES {
        let Some(rows) = read_json(dir, file, &mut problems) else {
            continue;
        };
        let rules: Vec<&Rule> = RULES.iter().filter(|rule| rule.file == file).collect();
        if rules.is_empty() {
            continue;
        }
        let Some(rows) = rows.as_array() else {
            problems.push(format!("{file} is not a JSON array"));
            continue;
        };
        for rule in rules {
            problems.extend(rule_problems(rule, rows));
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

/// One line per field the rule flags in at least one row, with the row count.
fn rule_problems(rule: &Rule, rows: &[Value]) -> Vec<String> {
    rule.fields
        .iter()
        .filter_map(|field| {
            let count = rows
                .iter()
                .filter(|row| row.get(field).is_some_and(rule.is_bad))
                .count();
            (count > 0).then(|| format!("{}: {count} rows have {} {field}", rule.file, rule.what))
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

/// True when a public location holds a number that could name a home. It fails closed: every
/// run of digits has to be one the public set uses, or the value fails. The allowed forms:
///
/// - the hundred in "1200 block of Main St", at the start of a comma-separated part;
/// - an ordinal, such as "1st" or "11th";
/// - a road number after Route, Rte, RT, NH, US, VT, I or Interstate;
/// - a number after Exit or "mile marker".
///
/// So "12 Main St", "12-14 Main St", "No. 12 Main St", "Smith Residence 12 Main St", "Lot 5"
/// and "Apt 12" fail, and so does any digit that is not ASCII.
fn has_unexplained_number(value: &Value) -> bool {
    value.as_str().is_some_and(|text| {
        text.chars().any(|c| !c.is_ascii() && c.is_numeric()) || has_unexplained_digits(text)
    })
}

fn has_unexplained_digits(text: &str) -> bool {
    let bytes = text.as_bytes();
    let mut end = 0;
    while end < bytes.len() {
        if !bytes[end].is_ascii_digit() {
            end += 1;
            continue;
        }
        let start = end;
        while end < bytes.len() && bytes[end].is_ascii_digit() {
            end += 1;
        }
        if !digits_are_explained(&text[..start], &text[start..end], &text[end..]) {
            return true;
        }
    }
    false
}

/// `digits` is one whole run of digits, with the text before and after it.
fn digits_are_explained(before: &str, digits: &str, after: &str) -> bool {
    is_block_hundred(before, digits, after)
        || is_ordinal(after)
        || matches!(
            last_word(before).as_str(),
            "route" | "rte" | "rt" | "nh" | "us" | "vt" | "i" | "interstate" | "exit" | "marker"
        )
}

/// The "1200" of "1200 block of Main St": a whole hundred with no leading zero, opening
/// a comma-separated part.
fn is_block_hundred(before: &str, digits: &str, after: &str) -> bool {
    let opens_part = before.trim_end().is_empty() || before.trim_end().ends_with(',');
    opens_part
        && digits.len() >= 3
        && !digits.starts_with('0')
        && digits.ends_with("00")
        && after.to_ascii_lowercase().starts_with(" block of ")
}

/// "1st", "2nd", "3rd", "11th": the digits are followed by an ordinal suffix and not more letters.
fn is_ordinal(after: &str) -> bool {
    let after = after.to_ascii_lowercase();
    ["st", "nd", "rd", "th"].iter().any(|suffix| {
        after
            .strip_prefix(suffix)
            .is_some_and(|rest| !rest.starts_with(|c: char| c.is_ascii_alphabetic()))
    })
}

/// The lowercase word just before a number, skipping spaces, hyphens and dots: "I-" gives "i".
fn last_word(before: &str) -> String {
    let before = before.trim_end_matches([' ', '-', '.']);
    let start = before
        .rfind(|c: char| !c.is_ascii_alphabetic())
        .map_or(0, |index| index + 1);
    before[start..].to_ascii_lowercase()
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

    #[test]
    fn a_house_number_in_an_incident_location_fails() {
        let dir = clean_export();
        write(
            &dir,
            "incidents.json",
            &json!([{"location": "12 Main St"}, {"location": "1200 block of Main St"}]),
        );

        assert_eq!(
            check_dir(dir.path()),
            vec!["incidents.json: 1 rows have an unexpected number in location"]
        );
    }

    #[test]
    fn a_house_number_in_an_address_name_fails_for_each_name_field() {
        let dir = clean_export();
        write(
            &dir,
            "addresses.json",
            &json!([{"raw_address": "12 Main St", "normalized_address": "45 Elm St"}]),
        );

        assert_eq!(
            check_dir(dir.path()),
            vec![
                "addresses.json: 1 rows have an unexpected number in raw_address",
                "addresses.json: 1 rows have an unexpected number in normalized_address",
            ]
        );
    }

    #[test]
    fn public_locations_with_only_allowed_numbers_pass() {
        let passing = [
            "1200 block of Main St",
            "100 block of Mascoma St",
            "Main St",
            "Main St and Hanover St",
            "Route 120",
            "NH Route 12A",
            "US Route 4",
            "Rte 4",
            "RT 4",
            "I-89 Exit 18",
            "Exit 18 on I-89",
            "I-89 mile marker 12",
            "Interstate 89",
            "1st Ave",
            "2nd St",
            "3rd Ave",
            "11th St",
            "Smith residence, Main St",
            "Smith residence, 1200 block of Main St",
        ];
        for location in passing {
            let dir = clean_export();
            write(&dir, "incidents.json", &json!([{"location": location}]));

            assert!(check_dir(dir.path()).is_empty(), "{location}");
        }
    }

    #[test]
    fn locations_with_any_other_number_fail() {
        let failing = [
            "12 Main St",
            "12B Main St",
            "12-14 Main St",
            "12 1/2 Main St",
            "No. 12 Main St",
            "#12 Main St",
            "Smith Residence 12 Main St",
            "Smith residence, 12 Main St",
            "Mascoma Apartments Apt 12",
            "Lot 5",
            "Route 12 Apt 5",
            "1050 block of Main St",
            "0200 block of Main St",
            "Smith residence 1200 block of Main St",
            "  45 Elm St",
            "\u{FF11}\u{FF12} Main St",
            "\u{0661}\u{0662} Main St",
        ];
        for location in failing {
            let dir = clean_export();
            write(&dir, "incidents.json", &json!([{"location": location}]));

            assert_eq!(check_dir(dir.path()).len(), 1, "{location}");
        }
    }

    #[test]
    fn a_missing_or_null_location_passes() {
        let dir = clean_export();
        write(
            &dir,
            "incidents.json",
            &json!([{"case_number": "26-1"}, {"location": null}]),
        );

        assert!(check_dir(dir.path()).is_empty());
    }
}
