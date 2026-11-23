//! A check that no export query skips the public rules.
//!
//! The rules (a flagged location publishes only its street, a type shows its plain name)
//! live in the views `public_locations` and `public_log_entries`. A query that read the
//! tables, or worked out a call category itself, would leave them out.

use std::fs;
use std::path::PathBuf;

const TABLES: [&str; 2] = ["log_entries", "address_normalizations"];
const FUNCTION: &str = "call_category(";

fn sql_files() -> Vec<(String, String)> {
    let dir = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("src/sql");
    let mut files: Vec<(String, String)> = fs::read_dir(&dir)
        .expect("src/sql is readable")
        .map(|entry| entry.expect("a directory entry").path())
        .filter(|path| path.extension().is_some_and(|ext| ext == "sql"))
        .map(|path| {
            let name = path.file_name().unwrap().to_string_lossy().into_owned();
            let text = fs::read_to_string(&path).expect("a readable query");
            (name, text)
        })
        .collect();
    files.sort();
    files
}

/// The query with its `--` comments removed, so a comment may name a table.
fn code_of(sql: &str) -> String {
    sql.lines()
        .map(|line| line.split("--").next().unwrap_or(""))
        .collect::<Vec<_>>()
        .join("\n")
}

fn is_identifier_char(c: char) -> bool {
    c.is_ascii_alphanumeric() || c == '_'
}

/// Whether `word` appears as a whole name, so `public_log_entries` is not `log_entries`.
fn names(code: &str, word: &str) -> bool {
    code.match_indices(word).any(|(start, _)| {
        let before = code[..start].chars().next_back();
        let after = code[start + word.len()..].chars().next();
        !before.is_some_and(is_identifier_char) && !after.is_some_and(is_identifier_char)
    })
}

#[test]
fn there_are_queries_to_check() {
    assert!(sql_files().len() >= 6);
}

#[test]
fn no_query_reads_a_table_directly() {
    for (name, sql) in sql_files() {
        let code = code_of(&sql);
        for table in TABLES {
            assert!(
                !names(&code, table),
                "{name} reads {table}. Read the public view instead."
            );
        }
    }
}

#[test]
fn no_query_works_out_a_call_category_itself() {
    for (name, sql) in sql_files() {
        assert!(
            !code_of(&sql).contains(FUNCTION),
            "{name} calls call_category(). Read the view's category column instead."
        );
    }
}

#[test]
fn every_query_reads_a_public_view() {
    for (name, sql) in sql_files() {
        let code = code_of(&sql);
        assert!(
            names(&code, "public_log_entries") || names(&code, "public_locations"),
            "{name} reads no public view."
        );
    }
}

#[test]
fn the_check_tells_a_view_from_a_table() {
    assert!(names("FROM log_entries le", "log_entries"));
    assert!(names(
        "JOIN address_normalizations an",
        "address_normalizations"
    ));
    assert!(!names("FROM public_log_entries le", "log_entries"));
    assert!(!names("FROM log_entries_archive", "log_entries"));
}

#[test]
fn a_comment_may_name_a_table_but_code_may_not() {
    assert!(!names(
        &code_of("-- reads log_entries\nSELECT 1"),
        "log_entries"
    ));
    assert!(names(
        &code_of("SELECT 1 FROM log_entries -- ok"),
        "log_entries"
    ));
}
