use anyhow::Result;
use chrono::NaiveDate;
use chrono::NaiveDateTime;
use serde::Serialize;
use sqlx::PgPool;

// ---- Stats ----

#[derive(Debug, Serialize)]
#[allow(clippy::struct_field_names)]
pub struct ByType {
    pub incident_type: String,
    pub count: i64,
}

#[derive(Debug, Serialize)]
pub struct ByWeekday {
    pub day: String,
    pub count: i64,
}

#[derive(Debug, Serialize)]
pub struct ByHour {
    pub hour: i32,
    pub count: i64,
}

#[derive(Debug, Serialize)]
pub struct Stats {
    pub total: i64,
    pub generated_at: String,
    // The first day the police log figures cover, as an ISO date.
    pub since: String,
    pub by_type: Vec<ByType>,
    pub by_weekday: Vec<ByWeekday>,
    // Calls by the hour of the day, 0 to 23, for the hours that had any.
    pub by_hour: Vec<ByHour>,
    // The entries in range that are on a pin, which is what the three lists above count.
    // `total` is every entry in range.
    pub mapped_total: i64,
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
    pub source_url: String,
}

// ---- Address ----

#[derive(Debug, Serialize, sqlx::FromRow)]
#[allow(clippy::struct_field_names)]
pub struct Address {
    // A slug of the normalized address, and the name of the place's card file.
    pub id: String,
    // "place", or "road" for a bare street, an intersection or a highway.
    pub kind: String,
    pub raw_address: String,
    pub normalized_address: Option<String>,
    // A place counts every call except road traffic, and a road counts every call.
    pub count: i64,
    // The traffic that is counted nowhere. For a place, the part with no street pin to
    // fold onto, usually none. For a road, all its traffic, which is inside `count`.
    pub traffic_count: i64,
    // The traffic at a place, folded or not, for its "stops nearby" line. Never in a sum.
    pub nearby_traffic: i64,
    pub lat: f64,
    pub lng: f64,
    // "approximate" when the point is only somewhere on the place's street.
    pub precision: String,
    // The street pin an approximate place hangs on, when it has one.
    pub street_id: Option<String>,
    // True when the place has no pin of its own and is listed on its street's card.
    pub hidden: bool,
}

// A pin with its report card, which is JSON text that goes into places/<id>.json, and every
// entry of the pin as JSON text, for activity.json.
#[derive(Debug, sqlx::FromRow)]
pub struct PlaceRow {
    #[sqlx(flatten)]
    pub address: Address,
    pub card: String,
    pub entries: String,
    // [reported_at or null, incident_type] of each entry, for stats.json.
    pub stat_entries: String,
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

pub const INCIDENT_LIMIT: i64 = 2000;

/// Every parsed entry in range, whether or not it is on a pin.
pub async fn fetch_total(pool: &PgPool, since: NaiveDate) -> Result<i64> {
    sqlx::query_scalar(include_str!("sql/stats_total.sql"))
        .bind(since)
        .fetch_one(pool)
        .await
        .map_err(Into::into)
}

pub async fn fetch_incidents(pool: &PgPool, since: NaiveDate) -> Result<Vec<Incident>> {
    sqlx::query_as::<_, Incident>(include_str!("sql/incidents.sql"))
        .bind(since)
        .bind(INCIDENT_LIMIT)
        .fetch_all(pool)
        .await
        .map_err(Into::into)
}

pub async fn fetch_places(pool: &PgPool, since: NaiveDate) -> Result<Vec<PlaceRow>> {
    sqlx::query_as::<_, PlaceRow>(include_str!("sql/places.sql"))
        .bind(since)
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
        FROM public_properties
        ORDER BY assessed_total DESC NULLS LAST
        ",
    )
    .fetch_all(pool)
    .await
    .map_err(Into::into)
}
