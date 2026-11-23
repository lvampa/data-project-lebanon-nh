#![deny(clippy::all, clippy::pedantic)]

mod activity;
mod db;
mod output;
#[cfg(test)]
mod public_rules;
mod stats;

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

    let total = db::fetch_total(&pool, args.since).await?;

    let incidents = db::fetch_incidents(&pool, args.since).await?;
    println!(
        "✓ incidents.json  ({} rows of {total} total, capped at {})",
        incidents.len(),
        db::INCIDENT_LIMIT
    );
    output::write_json(&args.output_dir, "incidents.json", &incidents)?;

    let places = db::fetch_places(&pool, args.since).await?;
    // The stats count the entries on a pin, so they come after the pins.
    let stats = stats::build(total, args.since, &places)?;
    println!(
        "✓ stats.json  ({} total incidents, {} on a pin)",
        stats.total, stats.mapped_total
    );
    output::write_json(&args.output_dir, "stats.json", &stats)?;
    let unfolded: i64 = places
        .iter()
        .filter(|place| place.address.kind == "place")
        .map(|place| place.address.traffic_count)
        .sum();
    if unfolded > 0 {
        println!("  {unfolded} place traffic entries have no street pin, and stay on the place");
    }
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
    println!(
        "✓ activity.json  ({} entries, {} of the {} in range are on the map)",
        activity.entries(),
        percent_on_map(activity.entries(), stats.total),
        stats.total
    );
    output::write_json_compact(&args.output_dir, "activity.json", &activity)?;

    let staff = db::fetch_staff(&pool).await?;
    println!("✓ staff.json  ({} rows)", staff.len());
    output::write_json(&args.output_dir, "staff.json", &staff)?;

    let properties = db::fetch_properties(&pool).await?;
    println!("✓ properties.json  ({} rows)", properties.len());
    output::write_json(&args.output_dir, "properties.json", &properties)?;

    Ok(())
}

/// The share of in-range entries that sit on a pin, in tenths of a percent: "92.3%".
fn percent_on_map(on_map: usize, total: i64) -> String {
    let total = u64::try_from(total).unwrap_or(0);
    if total == 0 {
        return "no entries".to_string();
    }
    let on_map = u64::try_from(on_map).unwrap_or(u64::MAX);
    let tenths = (on_map * 1000 + total / 2) / total;
    format!("{}.{}%", tenths / 10, tenths % 10)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_share_on_the_map_is_in_tenths_of_a_percent() {
        assert_eq!(percent_on_map(91, 100), "91.0%");
        assert_eq!(percent_on_map(923, 1000), "92.3%");
        assert_eq!(percent_on_map(2, 3), "66.7%");
        assert_eq!(percent_on_map(0, 10), "0.0%");
        assert_eq!(percent_on_map(10, 10), "100.0%");
    }

    #[test]
    fn the_share_on_the_map_with_no_entries_says_so() {
        assert_eq!(percent_on_map(0, 0), "no entries");
    }

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
