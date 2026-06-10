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

    let database_url =
        std::env::var("DATABASE_URL").map_err(|_| anyhow::anyhow!("DATABASE_URL not set"))?;

    let pool = sqlx::PgPool::connect(&database_url).await?;

    let stats = db::fetch_stats(&pool).await?;
    println!("✓ stats.json  ({} total incidents)", stats.total);
    output::write_json(&args.output_dir, "stats.json", &stats)?;

    let incidents = db::fetch_incidents(&pool).await?;
    println!("✓ incidents.json  ({} rows)", incidents.len());
    output::write_json(&args.output_dir, "incidents.json", &incidents)?;

    let addresses = db::fetch_addresses(&pool).await?;
    println!("✓ addresses.json  ({} rows)", addresses.len());
    output::write_json(&args.output_dir, "addresses.json", &addresses)?;

    let staff = db::fetch_staff(&pool).await?;
    println!("✓ staff.json  ({} rows)", staff.len());
    output::write_json(&args.output_dir, "staff.json", &staff)?;

    let properties = db::fetch_properties(&pool).await?;
    println!("✓ properties.json  ({} rows)", properties.len());
    output::write_json(&args.output_dir, "properties.json", &properties)?;

    Ok(())
}
