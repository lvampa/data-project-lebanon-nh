//! stats.json: the town's totals, and the charts the page draws from them.
//!
//! The three lists count the entries that are on a pin, the same base as `mapped_total` and
//! activity.json, so a chart and the map agree. `total` is every entry in range.

use crate::db::{ByHour, ByType, ByWeekday, PlaceRow, Stats};
use anyhow::{Context, Result};
use chrono::{Datelike, NaiveDate, NaiveDateTime, Timelike, Utc};
use std::collections::BTreeMap;

const DAYS: [&str; 7] = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
/// The most type names listed, "Other" after them.
const TOP_TYPES: usize = 20;
const OTHER: &str = "Other";

/// One entry as places.sql lists it for the stats: the report time, null when the log had
/// none, and the type.
type StatEntry = (Option<NaiveDateTime>, Option<String>);

pub fn build(total: i64, since: NaiveDate, places: &[PlaceRow]) -> Result<Stats> {
    let mut by_type: BTreeMap<String, i64> = BTreeMap::new();
    let mut by_weekday = [0_i64; 7];
    let mut by_hour: BTreeMap<u32, i64> = BTreeMap::new();
    let mut mapped_total = 0_i64;

    for place in places {
        let entries: Vec<StatEntry> = serde_json::from_str(&place.stat_entries)
            .with_context(|| format!("the stat entries of pin {}", place.address.id))?;
        for (reported_at, incident_type) in entries {
            mapped_total += 1;
            *by_type
                .entry(incident_type.unwrap_or_else(|| OTHER.to_string()))
                .or_default() += 1;
            // An entry with no report time has no weekday or hour, and still has a type.
            if let Some(at) = reported_at {
                by_weekday[at.weekday().num_days_from_sunday() as usize] += 1;
                *by_hour.entry(at.hour()).or_default() += 1;
            }
        }
    }

    Ok(Stats {
        total,
        generated_at: Utc::now().to_rfc3339(),
        since: since.to_string(),
        by_type: list_types(by_type),
        by_weekday: DAYS
            .iter()
            .zip(by_weekday)
            .filter(|(_, count)| *count > 0)
            .map(|(day, count)| ByWeekday {
                day: (*day).to_string(),
                count,
            })
            .collect(),
        by_hour: by_hour
            .into_iter()
            .map(|(hour, count)| ByHour {
                hour: i32::try_from(hour).unwrap_or_default(),
                count,
            })
            .collect(),
        mapped_total,
    })
}

/// The busiest names, then "Other", which is every type with no plain name. "Other" is last
/// whatever its count.
fn list_types(counts: BTreeMap<String, i64>) -> Vec<ByType> {
    let other = counts.get(OTHER).copied();
    let mut named: Vec<(String, i64)> = counts
        .into_iter()
        .filter(|(name, _)| name != OTHER)
        .collect();
    named.sort_by(|a, b| b.1.cmp(&a.1).then_with(|| a.0.cmp(&b.0)));
    named.truncate(TOP_TYPES);
    named
        .into_iter()
        .chain(other.map(|count| (OTHER.to_string(), count)))
        .map(|(incident_type, count)| ByType {
            incident_type,
            count,
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::db::Address;
    use serde_json::json;

    fn place(id: &str, stat_entries: &serde_json::Value) -> PlaceRow {
        PlaceRow {
            address: Address {
                id: id.into(),
                kind: "place".into(),
                raw_address: id.into(),
                normalized_address: Some(id.into()),
                count: 0,
                traffic_count: 0,
                nearby_traffic: 0,
                lat: 43.64,
                lng: -72.25,
                precision: "exact".into(),
                street_id: None,
                hidden: false,
            },
            card: "{}".into(),
            entries: "[]".into(),
            stat_entries: stat_entries.to_string(),
        }
    }

    fn since() -> NaiveDate {
        NaiveDate::from_ymd_opt(2026, 1, 1).unwrap()
    }

    #[test]
    fn the_lists_count_only_the_entries_on_a_pin_and_the_total_is_kept() {
        let places = [
            place(
                "ford",
                &json!([
                    ["2026-01-01T09:30:00", "Alarm"],
                    ["2026-01-01T09:45:00", "Alarm"]
                ]),
            ),
            place(
                "main-st",
                &json!([["2026-01-02T16:00:00", "Welfare check"]]),
            ),
        ];

        let stats = build(26_319, since(), &places).unwrap();

        assert_eq!(stats.total, 26_319);
        assert_eq!(stats.mapped_total, 3);
        let counted: i64 = stats.by_type.iter().map(|t| t.count).sum();
        assert_eq!(counted, 3);
    }

    #[test]
    fn a_weekday_is_named_from_sunday_and_only_days_with_calls_are_listed() {
        // 2026-01-01 is a Thursday, and 2026-01-04 a Sunday.
        let places = [place(
            "ford",
            &json!([
                ["2026-01-01T00:10:00", "Alarm"],
                ["2026-01-04T23:50:00", "Alarm"],
                ["2026-01-04T08:00:00", "Alarm"]
            ]),
        )];

        let stats = build(3, since(), &places).unwrap();

        let days: Vec<(&str, i64)> = stats
            .by_weekday
            .iter()
            .map(|d| (d.day.as_str(), d.count))
            .collect();
        assert_eq!(days, [("Sun", 2), ("Thu", 1)]);
    }

    #[test]
    fn the_hours_are_listed_in_order_with_only_hours_that_had_calls() {
        let places = [place(
            "ford",
            &json!([
                ["2026-01-02T16:30:00", "Alarm"],
                ["2026-01-02T16:59:00", "Alarm"],
                ["2026-01-01T00:00:00", "Alarm"]
            ]),
        )];

        let stats = build(3, since(), &places).unwrap();

        let hours: Vec<(i32, i64)> = stats.by_hour.iter().map(|h| (h.hour, h.count)).collect();
        assert_eq!(hours, [(0, 1), (16, 2)]);
    }

    #[test]
    fn an_entry_with_no_report_time_has_a_type_but_no_weekday_or_hour() {
        let places = [place("ford", &json!([[null, "Alarm"]]))];

        let stats = build(1, since(), &places).unwrap();

        assert_eq!(stats.mapped_total, 1);
        assert_eq!(stats.by_type.len(), 1);
        assert!(stats.by_weekday.is_empty());
        assert!(stats.by_hour.is_empty());
    }

    #[test]
    fn types_are_busiest_first_with_other_last_whatever_its_count() {
        let places = [place(
            "ford",
            &json!([
                [null, "Other"],
                [null, "Other"],
                [null, "Other"],
                [null, "Noise"],
                [null, "Alarm"],
                [null, "Alarm"]
            ]),
        )];

        let stats = build(6, since(), &places).unwrap();

        let types: Vec<(&str, i64)> = stats
            .by_type
            .iter()
            .map(|t| (t.incident_type.as_str(), t.count))
            .collect();
        assert_eq!(types, [("Alarm", 2), ("Noise", 1), ("Other", 3)]);
    }

    #[test]
    fn at_most_twenty_names_are_listed_and_other_comes_after_them() {
        let entries: Vec<serde_json::Value> = (0..25)
            .map(|n| json!([null, format!("Type {n:02}")]))
            .chain((0..10).map(|_| json!([null, "Other"])))
            .collect();
        let places = [place("ford", &json!(entries))];

        let stats = build(35, since(), &places).unwrap();

        assert_eq!(stats.by_type.len(), 21);
        assert_eq!(stats.by_type.last().unwrap().incident_type, "Other");
        assert!(
            stats.by_type[..20]
                .iter()
                .all(|t| t.incident_type != "Other")
        );
    }

    #[test]
    fn a_pin_with_unreadable_stat_entries_names_the_pin() {
        let places = [place("ford", &json!("not a list"))];

        let error = build(1, since(), &places).unwrap_err();

        assert!(format!("{error:#}").contains("pin ford"));
    }

    #[test]
    fn no_pins_is_an_empty_chart_and_a_total_of_zero_mapped() {
        let stats = build(5, since(), &[]).unwrap();

        assert_eq!(stats.mapped_total, 0);
        assert!(stats.by_type.is_empty());
    }
}
