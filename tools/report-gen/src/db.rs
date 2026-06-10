use anyhow::Result;
use serde::Serialize;
use sqlx::PgPool;

#[derive(Debug, Serialize)]
pub struct Summary {
    pub total_incidents: i64,
}

#[derive(Debug, Serialize)]
pub struct Incident {}

pub async fn fetch_summary(_pool: &PgPool) -> Result<Summary> {
    todo!()
}

pub async fn fetch_incidents(_pool: &PgPool) -> Result<Vec<Incident>> {
    todo!()
}
