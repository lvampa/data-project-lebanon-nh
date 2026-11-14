use anyhow::Result;
use chrono::NaiveDateTime;
use chrono::Utc;
use serde::Serialize;
use sqlx::PgPool;
use std::cmp::Reverse;

// ---- Stats ----

#[derive(Debug, PartialEq, Eq, Serialize)]
#[allow(clippy::struct_field_names)]
pub struct ByType {
    pub incident_type: String,
    pub count: i64,
}

#[derive(Debug, PartialEq, Eq, Serialize)]
pub struct ByCategory {
    /// Empty for incidents that are not normalized yet.
    pub category: Option<String>,
    pub count: i64,
}

#[derive(Debug, PartialEq, Eq, Serialize)]
pub struct ByWeekday {
    pub day: String,
    pub count: i64,
}

#[derive(Debug, Serialize)]
pub struct Stats {
    pub total: i64,
    pub generated_at: String,
    pub by_type: Vec<ByType>,
    pub by_category: Vec<ByCategory>,
    pub by_weekday: Vec<ByWeekday>,
}

/// One row of `marts.public_stats`: a count for one value of one dimension.
#[derive(Debug, sqlx::FromRow)]
pub struct StatRow {
    pub dimension: String,
    pub value: Option<String>,
    pub count: i64,
}

// ---- Incident ----

#[derive(Debug, Serialize, sqlx::FromRow)]
#[allow(clippy::struct_field_names)]
pub struct Incident {
    pub case_number: Option<String>,
    pub reported_at: Option<NaiveDateTime>,
    pub call_source: Option<String>,
    pub incident_type: Option<String>,
    pub disposition: Option<String>,
    pub location: Option<String>,
    /// Always empty: the public export never carries officers.
    pub officer: Option<String>,
    /// Always empty: the public export never carries reference numbers.
    pub reference_number: Option<String>,
    pub category: Option<String>,
    pub normalized_type: Option<String>,
    pub lat: Option<f64>,
    pub lng: Option<f64>,
    pub coordinate_precision: Option<String>,
    pub source_url: String,
}

// ---- Address ----

#[derive(Debug, Serialize, sqlx::FromRow)]
#[allow(clippy::struct_field_names)]
pub struct Address {
    pub raw_address: String,
    pub normalized_address: Option<String>,
    pub count: i64,
    pub lat: f64,
    pub lng: f64,
}

// ---- Staff ----

#[derive(Debug, Serialize, sqlx::FromRow)]
pub struct Staff {
    pub id: i32,
    pub name: String,
    pub title: Option<String>,
    pub department: String,
    pub division: Option<String>,
    pub email: Option<String>,
    pub phone: Option<String>,
    pub source_url: String,
}

// ---- Property ----

#[derive(Debug, Serialize, sqlx::FromRow)]
pub struct Property {
    pub parcel_id: String,
    pub location: Option<String>,
    /// Always empty: the public export never carries owner names.
    pub owner: Option<String>,
    /// Always empty: the public export never carries owner addresses.
    pub owner_address: Option<String>,
    pub land_use: Option<String>,
    pub lot_size_acres: Option<f64>,
    pub year_built: Option<i32>,
    pub building_sqft: Option<i32>,
    pub assessed_land: Option<i32>,
    pub assessed_building: Option<i32>,
    pub assessed_total: Option<i32>,
    pub assessment_year: Option<i32>,
    pub detail_url: Option<String>,
}

// ---- Stats shaping ----

const DAYS: [&str; 7] = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const TOP_TYPES: usize = 20;

/// Shapes the long `public_stats` table into the nested `stats.json` form.
///
/// `by_type` is the top 20 normalized type names and leaves out incidents with no
/// normalization yet; `by_category` keeps them, under an empty category.
pub fn shape_stats(rows: &[StatRow], total: i64, generated_at: String) -> Stats {
    let in_dimension = |name: &'static str| rows.iter().filter(move |row| row.dimension == name);

    let mut by_type: Vec<ByType> = in_dimension("normalized_type")
        .filter_map(|row| {
            row.value.clone().map(|incident_type| ByType {
                incident_type,
                count: row.count,
            })
        })
        .collect();
    by_type.sort_by(|a, b| {
        (Reverse(a.count), &a.incident_type).cmp(&(Reverse(b.count), &b.incident_type))
    });
    by_type.truncate(TOP_TYPES);

    let mut by_category: Vec<ByCategory> = in_dimension("category")
        .map(|row| ByCategory {
            category: row.value.clone(),
            count: row.count,
        })
        .collect();
    by_category.sort_by(|a, b| {
        (Reverse(a.count), a.category.is_none(), &a.category).cmp(&(
            Reverse(b.count),
            b.category.is_none(),
            &b.category,
        ))
    });

    let mut by_weekday: Vec<(usize, ByWeekday)> = in_dimension("weekday")
        .filter_map(|row| {
            let index: usize = row.value.as_deref()?.parse().ok()?;
            let day = (*DAYS.get(index)?).to_string();
            Some((
                index,
                ByWeekday {
                    day,
                    count: row.count,
                },
            ))
        })
        .collect();
    by_weekday.sort_by_key(|(index, _)| *index);

    Stats {
        total,
        generated_at,
        by_type,
        by_category,
        by_weekday: by_weekday.into_iter().map(|(_, entry)| entry).collect(),
    }
}

// ---- Query functions ----

pub async fn fetch_stats(pool: &PgPool) -> Result<Stats> {
    let total: i64 = sqlx::query_scalar("SELECT COUNT(*) FROM marts.public_incidents")
        .fetch_one(pool)
        .await?;

    let rows =
        sqlx::query_as::<_, StatRow>("SELECT dimension, value, count FROM marts.public_stats")
            .fetch_all(pool)
            .await?;

    Ok(shape_stats(&rows, total, Utc::now().to_rfc3339()))
}

pub async fn fetch_incidents(pool: &PgPool) -> Result<Vec<Incident>> {
    sqlx::query_as::<_, Incident>(
        r"
        SELECT case_number, reported_at, call_source, incident_type,
               disposition, location, officer, reference_number,
               category, normalized_type,
               lat::FLOAT8 AS lat, lng::FLOAT8 AS lng, coordinate_precision,
               source_url
        FROM marts.public_incidents
        ORDER BY reported_at DESC NULLS LAST
        ",
    )
    .fetch_all(pool)
    .await
    .map_err(Into::into)
}

pub async fn fetch_addresses(pool: &PgPool) -> Result<Vec<Address>> {
    sqlx::query_as::<_, Address>(
        r"
        SELECT raw_address, normalized_address, count,
               lat::FLOAT8 AS lat, lng::FLOAT8 AS lng
        FROM marts.public_addresses
        ORDER BY count DESC
        ",
    )
    .fetch_all(pool)
    .await
    .map_err(Into::into)
}

pub async fn fetch_staff(pool: &PgPool) -> Result<Vec<Staff>> {
    sqlx::query_as::<_, Staff>(
        r"
        SELECT id, name, title, department, division, email, phone, source_url
        FROM city_staff
        ORDER BY department, division, name
        ",
    )
    .fetch_all(pool)
    .await
    .map_err(Into::into)
}

pub async fn fetch_properties(pool: &PgPool) -> Result<Vec<Property>> {
    sqlx::query_as::<_, Property>(
        r"
        SELECT
            parcel_id, location, owner, owner_address, land_use,
            lot_size_acres, year_built, building_sqft,
            assessed_land, assessed_building, assessed_total, assessment_year,
            detail_url
        FROM marts.public_properties
        ORDER BY assessed_total DESC NULLS LAST
        ",
    )
    .fetch_all(pool)
    .await
    .map_err(Into::into)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn row(dimension: &str, value: Option<&str>, count: i64) -> StatRow {
        StatRow {
            dimension: dimension.to_string(),
            value: value.map(str::to_string),
            count,
        }
    }

    fn shape(rows: &[StatRow]) -> Stats {
        shape_stats(rows, 100, "2026-11-14T00:00:00+00:00".to_string())
    }

    #[test]
    fn total_and_time_pass_through() {
        let stats = shape(&[]);

        assert_eq!(stats.total, 100);
        assert_eq!(stats.generated_at, "2026-11-14T00:00:00+00:00");
        assert!(stats.by_type.is_empty() && stats.by_category.is_empty());
    }

    #[test]
    fn not_yet_normalized_incidents_are_left_out_of_by_type_and_kept_in_by_category() {
        let stats = shape(&[
            row("normalized_type", Some("Noise Complaint"), 5),
            row("normalized_type", None, 9),
            row("category", Some("Disturbance"), 5),
            row("category", None, 9),
        ]);

        assert_eq!(
            stats.by_type,
            vec![ByType {
                incident_type: "Noise Complaint".to_string(),
                count: 5
            }]
        );
        assert_eq!(
            stats.by_category,
            vec![
                ByCategory {
                    category: None,
                    count: 9
                },
                ByCategory {
                    category: Some("Disturbance".to_string()),
                    count: 5
                },
            ]
        );
    }

    #[test]
    fn by_type_is_the_top_twenty_by_count_with_ties_by_name() {
        let rows: Vec<StatRow> = (0..25)
            .map(|n| row("normalized_type", Some(&format!("Type {n:02}")), 100 - n))
            .chain([row("normalized_type", Some("Aardvark"), 100 - 24)])
            .collect();

        let stats = shape(&rows);

        assert_eq!(stats.by_type.len(), 20);
        assert_eq!(stats.by_type[0].incident_type, "Type 00");
        assert_eq!(stats.by_type[19].incident_type, "Type 19");
    }

    #[test]
    fn equal_counts_sort_by_name() {
        let stats = shape(&[
            row("normalized_type", Some("B"), 3),
            row("normalized_type", Some("A"), 3),
        ]);

        let names: Vec<&str> = stats
            .by_type
            .iter()
            .map(|t| t.incident_type.as_str())
            .collect();
        assert_eq!(names, ["A", "B"]);
    }

    #[test]
    fn weekdays_are_named_and_ordered_from_sunday() {
        let stats = shape(&[
            row("weekday", Some("6"), 1),
            row("weekday", Some("0"), 2),
            row("weekday", Some("3"), 3),
        ]);

        let days: Vec<(&str, i64)> = stats
            .by_weekday
            .iter()
            .map(|d| (d.day.as_str(), d.count))
            .collect();
        assert_eq!(days, [("Sun", 2), ("Wed", 3), ("Sat", 1)]);
    }

    #[test]
    fn an_unknown_weekday_value_is_skipped() {
        let stats = shape(&[
            row("weekday", Some("7"), 1),
            row("weekday", Some("x"), 1),
            row("weekday", None, 1),
        ]);

        assert!(stats.by_weekday.is_empty());
    }

    #[test]
    fn rows_of_other_dimensions_do_not_leak_into_a_list() {
        let stats = shape(&[row("category", Some("Traffic"), 4)]);

        assert!(stats.by_type.is_empty() && stats.by_weekday.is_empty());
        assert_eq!(stats.by_category.len(), 1);
    }
}
