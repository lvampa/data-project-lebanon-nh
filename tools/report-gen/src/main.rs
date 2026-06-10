#![deny(clippy::all, clippy::pedantic)]

mod db;
mod output;

use anyhow::Result;
use clap::Parser;
use std::path::PathBuf;

#[derive(Parser)]
#[command(about = "Generate static JSON report files from PostgreSQL")]
struct Args {
    /// Output directory for JSON files
    #[arg(long, default_value = "frontend/web/public/data")]
    output_dir: PathBuf,
}

#[tokio::main]
async fn main() -> Result<()> {
    let args = Args::parse();
    dotenvy::dotenv().ok();

    let database_url = std::env::var("DATABASE_URL")
        .map_err(|_| anyhow::anyhow!("DATABASE_URL not set"))?;

    let pool = sqlx::PgPool::connect(&database_url).await?;

    let summary = db::fetch_summary(&pool).await?;
    output::write_json(&args.output_dir, "summary.json", &summary)?;
    println!("✓ summary.json  ({} total incidents)", summary.total_incidents);

    let incidents = db::fetch_incidents(&pool).await?;
    println!("✓ incidents.json  ({} rows)", incidents.len());
    output::write_json(&args.output_dir, "incidents.json", &incidents)?;

    Ok(())
}
