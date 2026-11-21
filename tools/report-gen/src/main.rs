#![deny(clippy::all, clippy::pedantic)]

mod activity;
mod db;
mod output;

use anyhow::Result;
use chrono::NaiveDate;
use clap::Parser;
use std::path::PathBuf;

#[derive(Parser)]
#[command(about = "Generate static JSON report files from PostgreSQL")]
struct Args {
    /// Output directory for JSON files
    #[arg(long, default_value = "frontend/web/public/data")]
    output_dir: PathBuf,

    /// First day of police log data to publish, as YYYY-MM-DD
    #[arg(long, default_value = "2026-01-01")]
    since: NaiveDate,
}

#[tokio::main]
async fn main() -> Result<()> {
    let args = Args::parse();
    dotenvy::dotenv().ok();

    let database_url =
        std::env::var("DATABASE_URL").map_err(|_| anyhow::anyhow!("DATABASE_URL not set"))?;

    let pool = sqlx::PgPool::connect(&database_url).await?;

    let stats = db::fetch_stats(&pool, args.since).await?;
    println!("✓ stats.json  ({} total incidents)", stats.total);
    output::write_json(&args.output_dir, "stats.json", &stats)?;

    let incidents = db::fetch_incidents(&pool, args.since).await?;
    println!(
        "✓ incidents.json  ({} rows of {} total, capped at {})",
        incidents.len(),
        stats.total,
        db::INCIDENT_LIMIT
    );
    output::write_json(&args.output_dir, "incidents.json", &incidents)?;

    let places = db::fetch_places(&pool, args.since).await?;
    let addresses: Vec<&db::Address> = places.iter().map(|place| &place.address).collect();
    println!("✓ addresses.json  ({} rows)", addresses.len());
    output::write_json(&args.output_dir, "addresses.json", &addresses)?;

    let places_dir = args.output_dir.join("places");
    output::reset_dir(&places_dir)?;
    for place in &places {
        let card: serde_json::Value = serde_json::from_str(&place.card)?;
        output::write_json(&places_dir, &format!("{}.json", place.address.id), &card)?;
    }
    println!("✓ places/  ({} files)", places.len());

    let activity = activity::build(&places, args.since)?;
    println!("✓ activity.json  ({} entries)", activity.entries());
    output::write_json_compact(&args.output_dir, "activity.json", &activity)?;

    let staff = db::fetch_staff(&pool).await?;
    println!("✓ staff.json  ({} rows)", staff.len());
    output::write_json(&args.output_dir, "staff.json", &staff)?;

    let properties = db::fetch_properties(&pool).await?;
    println!("✓ properties.json  ({} rows)", properties.len());
    output::write_json(&args.output_dir, "properties.json", &properties)?;

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn since_defaults_to_the_start_of_2026() {
        let args = Args::try_parse_from(["report-gen"]).unwrap();
        assert_eq!(args.since, NaiveDate::from_ymd_opt(2026, 1, 1).unwrap());
    }

    #[test]
    fn since_takes_an_iso_date() {
        let args = Args::try_parse_from(["report-gen", "--since", "2025-12-01"]).unwrap();
        assert_eq!(args.since, NaiveDate::from_ymd_opt(2025, 12, 1).unwrap());
    }

    #[test]
    fn since_rejects_anything_else() {
        assert!(Args::try_parse_from(["report-gen", "--since", "last year"]).is_err());
    }
}
