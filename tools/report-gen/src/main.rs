#![deny(clippy::all, clippy::pedantic)]

mod check;
mod db;
mod output;

use anyhow::{Result, bail};
use clap::{Parser, Subcommand};
use std::path::{Path, PathBuf};

const DEFAULT_DIR: &str = "frontend/web/public/data";

/// The files `generate` writes. It clears these first, so a run that fails halfway
/// leaves them missing, which `check` catches, and never an old export.
const OUTPUT_FILES: [&str; 5] = [
    "stats.json",
    "incidents.json",
    "addresses.json",
    "staff.json",
    "properties.json",
];

#[derive(Parser)]
#[command(about = "Generate static JSON report files from PostgreSQL")]
struct Args {
    /// Output directory for JSON files
    #[arg(long, default_value = DEFAULT_DIR)]
    output_dir: PathBuf,

    #[command(subcommand)]
    command: Option<Command>,
}

#[derive(Subcommand)]
enum Command {
    /// Check the written files for fields that must be empty, before a deploy
    Check {
        /// Directory the JSON files were written to
        #[arg(long, default_value = DEFAULT_DIR)]
        dir: PathBuf,
    },
}

#[tokio::main]
async fn main() -> Result<()> {
    let args = Args::parse();
    match args.command {
        Some(Command::Check { dir }) => run_check(&dir),
        None => generate(&args.output_dir).await,
    }
}

fn run_check(dir: &Path) -> Result<()> {
    let problems = check::check_dir(dir);
    for problem in &problems {
        eprintln!("✗ {problem}");
    }
    if !problems.is_empty() {
        bail!(
            "pre-deploy check failed: {} problems in {}",
            problems.len(),
            dir.display()
        );
    }
    println!("✓ pre-deploy check passed ({})", dir.display());
    Ok(())
}

async fn generate(output_dir: &Path) -> Result<()> {
    dotenvy::dotenv().ok();

    let database_url =
        std::env::var("DATABASE_URL").map_err(|_| anyhow::anyhow!("DATABASE_URL not set"))?;

    let pool = sqlx::PgPool::connect(&database_url).await?;
    output::clear_files(output_dir, &OUTPUT_FILES)?;

    let stats = db::fetch_stats(&pool).await?;
    println!("✓ stats.json  ({} total incidents)", stats.total);
    output::write_json(output_dir, "stats.json", &stats)?;

    let incidents = db::fetch_incidents(&pool).await?;
    println!("✓ incidents.json  ({} rows)", incidents.len());
    output::write_json(output_dir, "incidents.json", &incidents)?;

    let addresses = db::fetch_addresses(&pool).await?;
    println!("✓ addresses.json  ({} rows)", addresses.len());
    output::write_json(output_dir, "addresses.json", &addresses)?;

    let staff = db::fetch_staff(&pool).await?;
    println!("✓ staff.json  ({} rows)", staff.len());
    output::write_json(output_dir, "staff.json", &staff)?;

    let properties = db::fetch_properties(&pool).await?;
    println!("✓ properties.json  ({} rows)", properties.len());
    output::write_json(output_dir, "properties.json", &properties)?;

    Ok(())
}
