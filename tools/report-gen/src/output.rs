use anyhow::Result;
use serde::Serialize;
use std::path::Path;

pub fn write_json<T: Serialize>(_dir: &Path, _filename: &str, _data: &T) -> Result<()> {
    todo!()
}
