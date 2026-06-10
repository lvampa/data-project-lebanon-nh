use anyhow::Result;
use serde::Serialize;
use sqlx::PgPool;

#[derive(Debug, Serialize)]
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

#[derive(Debug, Serialize)]
pub struct Incident {}

#[derive(Debug, Serialize)]
pub struct Address {}

#[derive(Debug, Serialize)]
pub struct Staff {}

#[derive(Debug, Serialize)]
pub struct Property {}

#[allow(clippy::unused_async)]
pub async fn fetch_stats(_pool: &PgPool) -> Result<Stats> {
    todo!()
}

#[allow(clippy::unused_async)]
pub async fn fetch_incidents(_pool: &PgPool) -> Result<Vec<Incident>> {
    todo!()
}

#[allow(clippy::unused_async)]
pub async fn fetch_addresses(_pool: &PgPool) -> Result<Vec<Address>> {
    todo!()
}

#[allow(clippy::unused_async)]
pub async fn fetch_staff(_pool: &PgPool) -> Result<Vec<Staff>> {
    todo!()
}

#[allow(clippy::unused_async)]
pub async fn fetch_properties(_pool: &PgPool) -> Result<Vec<Property>> {
    todo!()
}
