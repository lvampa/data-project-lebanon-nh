//! activity.json: every published log entry, in columns, for the police views' filters.
//!
//! Each column holds one value per entry, in the same order. Text values are written once,
//! in a lookup table, and the columns hold their index, which keeps the file small.

use crate::db::PlaceRow;
use anyhow::{Context, Result};
use chrono::{NaiveDate, NaiveDateTime};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// A response or a time on scene that has no times to work from.
const UNTIMED: i64 = -1;
/// Past this many minutes a response or a time on scene is a slip in the log, not a call.
const LONGEST_MINUTES: i64 = 600;
const INITIATED: &str = "Initiated";
const WALK_IN: &str = "Walk-In";

/// One entry, as places.sql lists it: a JSON array in this field order.
#[derive(Debug, Deserialize)]
pub struct Entry {
    /// The report time, or the log day at midnight when the entry has none.
    logged_at: NaiveDateTime,
    category: String,
    incident_type: Option<String>,
    disposition: Option<String>,
    call_source: Option<String>,
    officer: Option<String>,
    dispatched_at: Option<NaiveDateTime>,
    arrived_at: Option<NaiveDateTime>,
    cleared_at: Option<NaiveDateTime>,
}

#[derive(Debug, Serialize)]
pub struct Activity {
    since: String,
    /// The pin ids, in the order of addresses.json. `columns.pin` indexes into this.
    pins: Vec<String>,
    lookups: Lookups,
    columns: Columns,
}

#[derive(Debug, Serialize)]
struct Lookups {
    category: Vec<Option<String>>,
    #[serde(rename = "type")]
    incident_type: Vec<Option<String>>,
    disposition: Vec<Option<String>>,
    source: Vec<Option<String>>,
    officer: Vec<Option<String>>,
}

#[derive(Debug, Default, Serialize)]
struct Columns {
    pin: Vec<usize>,
    /// Minutes from `since` at midnight. Log times are New Hampshire local time.
    minute: Vec<i64>,
    category: Vec<usize>,
    #[serde(rename = "type")]
    incident_type: Vec<usize>,
    disposition: Vec<usize>,
    source: Vec<usize>,
    officer: Vec<usize>,
    response: Vec<i64>,
    scene: Vec<i64>,
}

/// Hands out one index per distinct value, in the order values are first seen.
#[derive(Default)]
struct Codes {
    values: Vec<Option<String>>,
    index: HashMap<Option<String>, usize>,
}

impl Codes {
    fn code(&mut self, value: Option<&str>) -> usize {
        let key = value.map(str::to_owned);
        if let Some(&found) = self.index.get(&key) {
            return found;
        }
        self.values.push(key.clone());
        self.index.insert(key, self.values.len() - 1);
        self.values.len() - 1
    }
}

pub fn build(places: &[PlaceRow], since: NaiveDate) -> Result<Activity> {
    let start = since.and_hms_opt(0, 0, 0).expect("midnight exists");
    let (mut category, mut incident_type, mut disposition, mut source, mut officer) = (
        Codes::default(),
        Codes::default(),
        Codes::default(),
        Codes::default(),
        Codes::default(),
    );
    let mut columns = Columns::default();

    for (pin, place) in places.iter().enumerate() {
        let entries: Vec<Entry> = serde_json::from_str(&place.entries)
            .with_context(|| format!("the entries of pin {}", place.address.id))?;
        for entry in &entries {
            columns.pin.push(pin);
            columns.minute.push((entry.logged_at - start).num_minutes());
            columns.category.push(category.code(Some(&entry.category)));
            columns
                .incident_type
                .push(incident_type.code(entry.incident_type.as_deref()));
            columns
                .disposition
                .push(disposition.code(entry.disposition.as_deref()));
            columns
                .source
                .push(source.code(entry.call_source.as_deref()));
            columns.officer.push(officer.code(entry.officer.as_deref()));
            columns.response.push(response_minutes(entry));
            columns.scene.push(scene_minutes(entry));
        }
    }

    Ok(Activity {
        since: since.to_string(),
        pins: places
            .iter()
            .map(|place| place.address.id.clone())
            .collect(),
        lookups: Lookups {
            category: category.values,
            incident_type: incident_type.values,
            disposition: disposition.values,
            source: source.values,
            officer: officer.values,
        },
        columns,
    })
}

impl Activity {
    pub fn entries(&self) -> usize {
        self.columns.pin.len()
    }
}

/// Minutes from dispatch to arrival, or from the log time when there was no dispatch.
fn response_minutes(entry: &Entry) -> i64 {
    // An officer who started the entry was already there, and a walk-in came to the station.
    if matches!(entry.call_source.as_deref(), Some(INITIATED | WALK_IN)) {
        return UNTIMED;
    }
    let Some(arrived) = entry.arrived_at else {
        return UNTIMED;
    };
    minutes_between(entry.dispatched_at.unwrap_or(entry.logged_at), arrived)
}

/// Minutes from arrival to clearing. An officer who started the entry was there from its
/// log time, so that stands in for a missing arrival.
fn scene_minutes(entry: &Entry) -> i64 {
    let started_by_officer = entry.call_source.as_deref() == Some(INITIATED);
    let begin = entry
        .arrived_at
        .or_else(|| started_by_officer.then_some(entry.logged_at));
    match (begin, entry.cleared_at) {
        (Some(begin), Some(cleared)) => minutes_between(begin, cleared),
        _ => UNTIMED,
    }
}

fn minutes_between(from: NaiveDateTime, to: NaiveDateTime) -> i64 {
    let minutes = (to - from).num_minutes();
    if (0..=LONGEST_MINUTES).contains(&minutes) {
        minutes
    } else {
        UNTIMED
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::db::Address;
    use serde_json::json;

    fn at(hour: u32, minute: u32) -> NaiveDateTime {
        NaiveDate::from_ymd_opt(2026, 6, 1)
            .unwrap()
            .and_hms_opt(hour, minute, 0)
            .unwrap()
    }

    fn entry(source: Option<&str>) -> Entry {
        Entry {
            logged_at: at(12, 0),
            category: "premises".into(),
            incident_type: Some("Welfare Check".into()),
            disposition: Some("Investigated".into()),
            call_source: source.map(str::to_owned),
            officer: Some("C. Day".into()),
            dispatched_at: None,
            arrived_at: None,
            cleared_at: None,
        }
    }

    fn place(id: &str, entries: &serde_json::Value) -> PlaceRow {
        PlaceRow {
            address: Address {
                id: id.into(),
                kind: "place".into(),
                raw_address: id.into(),
                normalized_address: Some(id.into()),
                count: 0,
                traffic_count: 0,
                lat: 43.64,
                lng: -72.25,
                precision: "exact".into(),
                street_id: None,
                hidden: false,
            },
            card: "{}".into(),
            entries: entries.to_string(),
        }
    }

    fn since() -> NaiveDate {
        NaiveDate::from_ymd_opt(2026, 1, 1).unwrap()
    }

    // --- response ---

    #[test]
    fn response_runs_from_dispatch_to_arrival() {
        let mut call = entry(Some("Telephone"));
        call.dispatched_at = Some(at(12, 2));
        call.arrived_at = Some(at(12, 9));
        assert_eq!(response_minutes(&call), 7);
    }

    #[test]
    fn response_runs_from_the_log_time_when_there_was_no_dispatch() {
        let mut call = entry(Some("911"));
        call.arrived_at = Some(at(12, 6));
        assert_eq!(response_minutes(&call), 6);
    }

    #[test]
    fn an_entry_an_officer_started_or_a_walk_in_has_no_response() {
        for source in [INITIATED, WALK_IN] {
            let mut call = entry(Some(source));
            call.arrived_at = Some(at(12, 6));
            assert_eq!(response_minutes(&call), UNTIMED, "{source}");
        }
    }

    #[test]
    fn a_call_with_no_arrival_has_no_response() {
        assert_eq!(response_minutes(&entry(Some("Telephone"))), UNTIMED);
    }

    #[test]
    fn an_arrival_before_dispatch_or_past_ten_hours_has_no_response() {
        let mut early = entry(Some("Telephone"));
        early.dispatched_at = Some(at(12, 10));
        early.arrived_at = Some(at(12, 5));
        assert_eq!(response_minutes(&early), UNTIMED);

        let mut late = entry(Some("Telephone"));
        late.arrived_at = Some(at(22, 1));
        assert_eq!(response_minutes(&late), UNTIMED);
    }

    // --- time on scene ---

    #[test]
    fn scene_runs_from_arrival_to_clearing() {
        let mut call = entry(Some("Telephone"));
        call.arrived_at = Some(at(12, 9));
        call.cleared_at = Some(at(12, 40));
        assert_eq!(scene_minutes(&call), 31);
    }

    #[test]
    fn an_entry_an_officer_started_is_on_scene_from_its_log_time() {
        let mut stop = entry(Some(INITIATED));
        stop.cleared_at = Some(at(12, 15));
        assert_eq!(scene_minutes(&stop), 15);
    }

    #[test]
    fn a_call_with_no_arrival_or_no_clearing_has_no_scene_time() {
        let mut no_arrival = entry(Some("Telephone"));
        no_arrival.cleared_at = Some(at(12, 15));
        assert_eq!(scene_minutes(&no_arrival), UNTIMED);

        let mut no_clearing = entry(Some("Telephone"));
        no_clearing.arrived_at = Some(at(12, 5));
        assert_eq!(scene_minutes(&no_clearing), UNTIMED);
    }

    #[test]
    fn a_scene_of_ten_hours_is_kept_and_longer_is_a_slip() {
        let mut shift = entry(Some(INITIATED));
        shift.cleared_at = Some(at(22, 0));
        assert_eq!(scene_minutes(&shift), 600);
        shift.cleared_at = Some(at(22, 1));
        assert_eq!(scene_minutes(&shift), UNTIMED);
    }

    // --- the file ---

    #[test]
    fn every_column_has_one_value_per_entry_and_pins_follow_addresses() {
        let places = [
            place(
                "ford",
                &json!([
                    [
                        "2026-01-01T00:30:00",
                        "premises",
                        "Welfare Check",
                        "Investigated",
                        "Telephone",
                        "C. Day",
                        "2026-01-01T00:31:00",
                        "2026-01-01T00:40:00",
                        "2026-01-01T01:00:00"
                    ],
                    [
                        "2026-01-02T08:00:00",
                        "traffic",
                        "Motor Vehicle Stop",
                        null,
                        "Initiated",
                        null,
                        null,
                        null,
                        "2026-01-02T08:12:00"
                    ]
                ]),
            ),
            place(
                "main-st",
                &json!([[
                    "2026-01-03T09:00:00",
                    "premises",
                    "Welfare Check",
                    null,
                    null,
                    "C. Day",
                    null,
                    null,
                    null
                ]]),
            ),
        ];

        let activity = build(&places, since()).unwrap();
        let columns = &activity.columns;

        assert_eq!(activity.pins, ["ford", "main-st"]);
        assert_eq!(activity.entries(), 3);
        for length in [
            columns.minute.len(),
            columns.category.len(),
            columns.incident_type.len(),
            columns.disposition.len(),
            columns.source.len(),
            columns.officer.len(),
            columns.response.len(),
            columns.scene.len(),
        ] {
            assert_eq!(length, 3);
        }
        assert_eq!(columns.pin, [0, 0, 1]);
        assert_eq!(columns.minute, [30, 24 * 60 + 8 * 60, 2 * 24 * 60 + 9 * 60]);
        assert_eq!(columns.response, [9, UNTIMED, UNTIMED]);
        assert_eq!(columns.scene, [20, 12, UNTIMED]);
    }

    #[test]
    fn a_value_is_written_once_and_a_missing_one_is_null() {
        let places = [place(
            "ford",
            &json!([
                [
                    "2026-01-01T00:30:00",
                    "premises",
                    "Welfare Check",
                    null,
                    null,
                    "C. Day",
                    null,
                    null,
                    null
                ],
                [
                    "2026-01-01T01:30:00",
                    "premises",
                    "Welfare Check",
                    null,
                    null,
                    null,
                    null,
                    null,
                    null
                ],
                [
                    "2026-01-01T02:30:00",
                    "alarms",
                    "Alarm",
                    null,
                    null,
                    "C. Day",
                    null,
                    null,
                    null
                ]
            ]),
        )];

        let activity = build(&places, since()).unwrap();

        assert_eq!(activity.lookups.officer, [Some("C. Day".to_owned()), None]);
        assert_eq!(activity.columns.officer, [0, 1, 0]);
        assert_eq!(activity.columns.incident_type, [0, 0, 1]);
        assert_eq!(activity.lookups.category.len(), 2);
    }

    #[test]
    fn the_file_names_its_columns_as_the_frontend_reads_them() {
        let places = [place(
            "ford",
            &json!([[
                "2026-01-01T00:30:00",
                "premises",
                "Welfare Check",
                null,
                null,
                null,
                null,
                null,
                null
            ]]),
        )];

        let written = serde_json::to_value(build(&places, since()).unwrap()).unwrap();

        assert_eq!(written["since"], "2026-01-01");
        assert_eq!(written["lookups"]["type"], json!(["Welfare Check"]));
        assert_eq!(written["columns"]["type"], json!([0]));
        assert!(written["columns"]["incident_type"].is_null());
    }

    #[test]
    fn a_pin_with_unreadable_entries_names_the_pin() {
        let places = [place("ford", &json!("not a list"))];
        let error = build(&places, since()).unwrap_err();
        assert!(format!("{error:#}").contains("pin ford"));
    }
}
