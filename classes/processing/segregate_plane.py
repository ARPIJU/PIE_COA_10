"""
Module for segregating flight data by aircraft tail number.

Provides functions to split combined flight data into separate files
for each aircraft, enabling plane-specific analysis.
"""

import logging
from pathlib import Path
import pandas as pd
from classes.analysis.reporting import Reporter


def segregate_plane_data(df_txt, tail_numbers, output_dir=None):
    """
    Segregates flight data by tail number and saves each to a separate CSV file.
    
    Parameters:
    -----------
    df_txt : pd.DataFrame
        DataFrame containing flight data with tail_number column
    tail_numbers : list
        List of tail numbers to segregate (e.g., from excel_sheets_priority)
    output_dir : str or Path, optional
        Directory to save the segregated CSV files. If None, uses workspace outputs directory.
    
    Returns:
    --------
    dict
        Dictionary mapping tail_number to output file path
    
    Raises:
    -------
    ValueError
        If df_txt doesn't contain tail_number column or data is empty
    """
    logger = logging.getLogger(__name__)
    
    if df_txt.empty:
        raise ValueError("DataFrame is empty")
    
    if "tail_number" not in df_txt.columns:
        raise ValueError("DataFrame missing 'tail_number' column")
    
    if output_dir is None:
        output_dir = Path(__file__).resolve().parent.parent.parent / "outputs"
    else:
        output_dir = Path(output_dir)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create Reporter instance for CSV export
    reporter = Reporter(output_dir)
    
    output_files = {}
    
    for tail_number in tail_numbers:
        # Filter data for this tail number
        df_plane = df_txt[df_txt["tail_number"] == tail_number].copy()
        
        if df_plane.empty:
            logger.warning(f"No data found for tail number: {tail_number}")
            continue
        
        # Export using reporter
        filename = f"data_processed_{tail_number}.csv"
        reporter.export_csv(df_plane, filename=filename)
        
        output_file = output_dir / filename
        output_files[tail_number] = output_file
        
        logger.info(f"Saved {len(df_plane)} records for tail number {tail_number}")
    
    logger.info(f"Segregation complete: {len(output_files)} files created")
    return output_files
