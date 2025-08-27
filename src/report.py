"""
Report generation module for Weekly Stocks project.
Creates CSV and HTML reports from stock data.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import config

logger = logging.getLogger(__name__)

class ReportGenerator:
    """Handles generation of CSV and HTML reports."""
    
    def __init__(self):
        # Set up Jinja2 environment
        template_dir = config.project_root / 'templates'
        self.jinja_env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(['html', 'xml'])
        )
    
    def save_csv_reports(self, weekly_data: pd.DataFrame, summary_stats: pd.DataFrame) -> Dict[str, Path]:
        """
        Save CSV reports to the output directory.
        
        Args:
            weekly_data: Weekly stock data DataFrame
            summary_stats: Summary statistics DataFrame
            
        Returns:
            Dictionary with paths to saved files
        """
        output_dir = config.today_output_dir
        saved_files = {}
        
        try:
            # Save weekly data
            if not weekly_data.empty:
                weekly_csv_path = output_dir / 'weekly_data.csv'
                weekly_data.to_csv(weekly_csv_path, index=False)
                saved_files['weekly_data'] = weekly_csv_path
                logger.info(f"Saved weekly data CSV: {weekly_csv_path}")
            
            # Save summary statistics
            if not summary_stats.empty:
                summary_csv_path = output_dir / 'summary_stats.csv'
                summary_stats.to_csv(summary_csv_path, index=False)
                saved_files['summary_stats'] = summary_csv_path
                logger.info(f"Saved summary stats CSV: {summary_csv_path}")
            
        except Exception as e:
            logger.error(f"Error saving CSV reports: {e}")
            raise
        
        return saved_files
    
    def generate_html_report(
        self, 
        weekly_data: pd.DataFrame, 
        summary_stats: pd.DataFrame, 
        status: Dict[str, Any]
    ) -> Path:
        """
        Generate HTML report using Jinja2 template.
        
        Args:
            weekly_data: Weekly stock data DataFrame
            summary_stats: Summary statistics DataFrame
            status: Status information from data fetching
            
        Returns:
            Path to generated HTML file
        """
        try:
            # Load template
            template = self.jinja_env.get_template('report.html')
            
            # Prepare template context
            now = datetime.now()
            context = {
                'report_date': now.strftime('%Y-%m-%d'),
                'report_time': now.strftime('%H:%M:%S'),
                'start_date': config.start_date,
                'end_date': config.end_date,
                'weekly_data': weekly_data,
                'summary_stats': summary_stats,
                'status': status,
                'config': config
            }
            
            # Render template
            html_content = template.render(**context)
            
            # Save HTML file
            html_path = config.today_output_dir / 'weekly_stocks_report.html'
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logger.info(f"Generated HTML report: {html_path}")
            return html_path
            
        except Exception as e:
            logger.error(f"Error generating HTML report: {e}")
            raise
    
    def create_summary_text(self, summary_stats: pd.DataFrame, status: Dict[str, Any]) -> str:
        """
        Create a text summary of the analysis.
        
        Args:
            summary_stats: Summary statistics DataFrame
            status: Status information from data fetching
            
        Returns:
            Text summary string
        """
        if summary_stats.empty:
            return "No data available for summary."
        
        # Calculate overall statistics
        avg_return = summary_stats['Total_Return_Pct'].mean()
        best_performer = summary_stats.iloc[0]  # Already sorted by total return
        worst_performer = summary_stats.iloc[-1]
        
        summary_lines = [
            f"Weekly Stocks Analysis Summary",
            f"=" * 40,
            f"Data Period: {config.start_date} to {config.end_date}",
            f"Stocks Analyzed: {status['total_successful']}/{status['total_requested']}",
            "",
            f"Overall Performance:",
            f"  Average Total Return: {avg_return:.2f}%",
            f"  Best Performer: {best_performer['Ticker']} ({best_performer['Total_Return_Pct']:.2f}%)",
            f"  Worst Performer: {worst_performer['Ticker']} ({worst_performer['Total_Return_Pct']:.2f}%)",
            "",
            f"Top 5 Performers:",
        ]
        
        # Add top 5 performers
        for i, row in summary_stats.head(5).iterrows():
            summary_lines.append(f"  {i+1}. {row['Ticker']}: {row['Total_Return_Pct']:.2f}%")
        
        if status['failed']:
            summary_lines.extend([
                "",
                f"Failed to fetch data for: {', '.join(status['failed'])}"
            ])
        
        return "\n".join(summary_lines)
    
    def save_summary_text(self, summary_stats: pd.DataFrame, status: Dict[str, Any]) -> Path:
        """
        Save text summary to file.
        
        Args:
            summary_stats: Summary statistics DataFrame
            status: Status information from data fetching
            
        Returns:
            Path to saved text file
        """
        try:
            summary_text = self.create_summary_text(summary_stats, status)
            summary_path = config.today_output_dir / 'summary.txt'
            
            with open(summary_path, 'w', encoding='utf-8') as f:
                f.write(summary_text)
            
            logger.info(f"Saved text summary: {summary_path}")
            return summary_path
            
        except Exception as e:
            logger.error(f"Error saving text summary: {e}")
            raise
    
    def generate_all_reports(
        self, 
        weekly_data: pd.DataFrame, 
        summary_stats: pd.DataFrame, 
        status: Dict[str, Any]
    ) -> Dict[str, Path]:
        """
        Generate all report formats.
        
        Args:
            weekly_data: Weekly stock data DataFrame
            summary_stats: Summary statistics DataFrame
            status: Status information from data fetching
            
        Returns:
            Dictionary with paths to all generated files
        """
        logger.info("Generating all reports...")
        
        all_files = {}
        
        # Generate CSV reports
        csv_files = self.save_csv_reports(weekly_data, summary_stats)
        all_files.update(csv_files)
        
        # Generate HTML report
        html_file = self.generate_html_report(weekly_data, summary_stats, status)
        all_files['html_report'] = html_file
        
        # Generate text summary
        text_file = self.save_summary_text(summary_stats, status)
        all_files['text_summary'] = text_file
        
        logger.info(f"Generated {len(all_files)} report files in {config.today_output_dir}")
        
        return all_files
