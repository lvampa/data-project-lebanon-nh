use anyhow::Result;
use chrono::NaiveDateTime;
use chrono::Utc;
use serde::Serialize;
use sqlx::PgPool;

// ---- Stats ----

#[derive(Debug, Serialize)]
#[allow(clippy::struct_field_names)]
pub struct ByType {
    pub incident_type: Option<String>,
    pub count: i64,
}

#[derive(Debug, Serialize)]
pub struct ByWeekday {
    pub day: String,
    pub count: i64,
}

#[derive(Debug, Serialize)]
pub struct Stats {
    pub total: i64,
    pub generated_at: String,
    pub by_type: Vec<ByType>,
    pub by_weekday: Vec<ByWeekday>,
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
    pub officer: Option<String>,
    pub reference_number: Option<String>,
    pub source_url: Option<String>,
}

// ---- Address ----

#[derive(Debug, Serialize, sqlx::FromRow)]
#[allow(clippy::struct_field_names)]
pub struct Address {
    pub raw_address: Option<String>,
    pub normalized_address: Option<String>,
    pub count: i64,
    pub lat: Option<f64>,
    pub lng: Option<f64>,
}

// ---- Staff ----

#[derive(Debug, Serialize, sqlx::FromRow)]
pub struct Staff {
    pub id: i32,
    pub name: Option<String>,
    pub title: Option<String>,
    pub department: Option<String>,
    pub division: Option<String>,
    pub email: Option<String>,
    pub phone: Option<String>,
    pub source_url: Option<String>,
}

// ---- Property ----

#[derive(Debug, Serialize, sqlx::FromRow)]
pub struct Property {
    pub parcel_id: Option<String>,
    pub location: Option<String>,
    pub owner: Option<String>,
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

// ---- Query functions ----

pub async fn fetch_stats(pool: &PgPool) -> Result<Stats> {
    const DAYS: [&str; 7] = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

    let total: i64 =
        sqlx::query_scalar("SELECT COUNT(*) FROM log_entries WHERE parse_error = false")
            .fetch_one(pool)
            .await?;

    let by_type_rows = sqlx::query_as::<_, (Option<String>, i64)>(
        r"
        SELECT incident_type, COUNT(*) AS count
        FROM log_entries
        WHERE parse_error = false AND incident_type IS NOT NULL
        GROUP BY incident_type
        ORDER BY count DESC
        LIMIT 20
        ",
    )
    .fetch_all(pool)
    .await?;

    let by_weekday_rows = sqlx::query_as::<_, (f64, i64)>(
        r"
        SELECT EXTRACT(DOW FROM reported_at) AS dow, COUNT(*) AS count
        FROM log_entries
        WHERE parse_error = false AND reported_at IS NOT NULL
        GROUP BY dow
        ORDER BY dow
        ",
    )
    .fetch_all(pool)
    .await?;

    Ok(Stats {
        total,
        generated_at: Utc::now().to_rfc3339(),
        by_type: by_type_rows
            .into_iter()
            .map(|(t, c)| ByType {
                incident_type: t,
                count: c,
            })
            .collect(),
        by_weekday: by_weekday_rows
            .into_iter()
            .map(|(dow, c)| ByWeekday {
                #[allow(clippy::cast_sign_loss, clippy::cast_possible_truncation)]
                day: DAYS[dow as usize].to_string(),
                count: c,
            })
            .collect(),
    })
}

pub async fn fetch_incidents(pool: &PgPool) -> Result<Vec<Incident>> {
    sqlx::query_as::<_, Incident>(
        r"
        SELECT case_number, reported_at, call_source, incident_type,
               disposition, location, officer, reference_number, source_url
        FROM log_entries
        WHERE parse_error = false
        ORDER BY reported_at DESC
        LIMIT 2000
        ",
    )
    .fetch_all(pool)
    .await
    .map_err(Into::into)
}

pub async fn fetch_addresses(pool: &PgPool) -> Result<Vec<Address>> {
    sqlx::query_as::<_, Address>(
        r"
        SELECT
            le.location         AS raw_address,
            an.normalized_address,
            COUNT(*)            AS count,
            an.lat,
            an.lng
        FROM log_entries le
        LEFT JOIN address_normalizations an
            ON le.location = an.raw_address
        WHERE le.location IS NOT NULL
          AND an.lat IS NOT NULL
          AND an.lng IS NOT NULL
        GROUP BY le.location, an.normalized_address, an.lat, an.lng
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
            lot_size_acres::FLOAT8 AS lot_size_acres,
            year_built, building_sqft,
            assessed_land, assessed_building, assessed_total, assessment_year,
            detail_url
        FROM properties
        ORDER BY assessed_total DESC NULLS LAST
        ",
    )
    .fetch_all(pool)
    .await
    .map_err(Into::into)
}
