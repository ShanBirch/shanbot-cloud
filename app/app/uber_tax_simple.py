import pandas as pd
from datetime import datetime, timedelta
import calendar


def create_uber_tax_template():
    """Create a comprehensive Uber tax reimbursement Excel template using pandas"""

    print("Creating Uber Tax Reimbursement Template...")

    # Create the main tracking data with sample entries
    sample_data = {
        'Date': ['2024-01-15', '2024-01-15', '2024-01-16'],
        'Time': ['09:30', '15:45', '19:20'],
        'Pickup Location': ['Home', 'CBD', 'Restaurant'],
        'Dropoff Location': ['Client Meeting - CBD', 'Airport', 'Home'],
        'Trip Purpose': ['Client Meeting', 'Business Travel', 'Dinner'],
        'Business/Personal': ['Business', 'Business', 'Personal'],
        'Uber Fare': [25.50, 45.80, 18.30],
        'Tips': [3.00, 5.00, 2.00],
        'Receipt #': ['UBR001', 'UBR002', 'UBR003'],
        'Notes': ['Meeting with ABC Corp', 'Flight to Sydney', 'Personal dinner']
    }

    # Create main tracking dataframe
    df_main = pd.DataFrame(sample_data)

    # Add calculated columns
    df_main['Total Cost'] = df_main['Uber Fare'] + df_main['Tips']
    df_main['Reimbursable'] = df_main.apply(
        lambda row: row['Total Cost'] if row['Business/Personal'] == 'Business' else 0, axis=1)
    df_main['Date'] = pd.to_datetime(df_main['Date'])
    df_main['Month'] = df_main['Date'].dt.month
    df_main['Week'] = df_main['Date'].dt.isocalendar().week

    # Create monthly summary
    months = [calendar.month_name[i] for i in range(1, 13)]
    monthly_data = {
        'Month': months,
        'Total Trips': [0] * 12,
        'Business Trips': [0] * 12,
        'Personal Trips': [0] * 12,
        'Total Amount': [0.0] * 12,
        'Reimbursable Amount': [0.0] * 12
    }

    # Calculate actual monthly totals from sample data
    for index, row in df_main.iterrows():
        month_idx = row['Month'] - 1
        monthly_data['Total Trips'][month_idx] += 1
        monthly_data['Total Amount'][month_idx] += row['Total Cost']
        if row['Business/Personal'] == 'Business':
            monthly_data['Business Trips'][month_idx] += 1
            monthly_data['Reimbursable Amount'][month_idx] += row['Total Cost']
        else:
            monthly_data['Personal Trips'][month_idx] += 1

    df_monthly = pd.DataFrame(monthly_data)

    # Create tax summary data
    business_trips = df_main[df_main['Business/Personal'] == 'Business']
    personal_trips = df_main[df_main['Business/Personal'] == 'Personal']

    tax_summary = {
        'Category': [
            'Total Business Trips',
            'Total Business Amount',
            'Average per Business Trip',
            '',
            'Total Personal Trips',
            'Total Personal Amount',
            '',
            'TOTAL REIMBURSABLE'
        ],
        'Amount': [
            len(business_trips),
            business_trips['Total Cost'].sum(),
            business_trips['Total Cost'].mean() if len(
                business_trips) > 0 else 0,
            '',
            len(personal_trips),
            personal_trips['Total Cost'].sum(),
            '',
            business_trips['Total Cost'].sum()
        ]
    }

    df_tax = pd.DataFrame(tax_summary)

    # Create filename with current year
    filename = f"Uber_Tax_Reimbursement_Template_{datetime.now().strftime('%Y')}.xlsx"

    # Write to Excel with multiple sheets
    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        # Main tracking sheet
        df_main.to_excel(
            writer, sheet_name='Uber Expense Tracker', index=False)

        # Monthly summary sheet
        df_monthly.to_excel(
            writer, sheet_name='Monthly Summary', index=False, startrow=4)

        # Tax summary sheet
        df_tax.to_excel(writer, sheet_name='Tax Summary',
                        index=False, startrow=6)

        # Get the workbook and worksheets for formatting
        workbook = writer.book

        # Format the main tracking sheet
        main_ws = workbook['Uber Expense Tracker']

        # Format currency columns
        for row in main_ws.iter_rows(min_row=2, max_row=main_ws.max_row, min_col=7, max_col=8):
            for cell in row:
                cell.number_format = '$#,##0.00'

        for row in main_ws.iter_rows(min_row=2, max_row=main_ws.max_row, min_col=11, max_col=12):
            for cell in row:
                cell.number_format = '$#,##0.00'

        # Format the monthly summary sheet
        monthly_ws = workbook['Monthly Summary']
        monthly_ws.cell(row=1, column=1, value="MONTHLY UBER EXPENSE SUMMARY")
        monthly_ws.cell(row=3, column=1, value=f"Year: {datetime.now().year}")

        # Format currency columns in monthly summary
        for row in monthly_ws.iter_rows(min_row=6, max_row=monthly_ws.max_row, min_col=5, max_col=6):
            for cell in row:
                cell.number_format = '$#,##0.00'

        # Format the tax summary sheet
        tax_ws = workbook['Tax Summary']
        tax_ws.cell(row=1, column=1, value="TAX & REIMBURSEMENT SUMMARY")
        tax_ws.cell(row=3, column=1, value=f"Tax Year: {datetime.now().year}")
        tax_ws.cell(row=5, column=1, value="BUSINESS EXPENSE SUMMARY")

        # Add instructions to tax summary
        instructions = [
            "",
            "INSTRUCTIONS FOR USE:",
            "1. Enter each Uber trip in the 'Uber Expense Tracker' sheet",
            "2. Categorize each trip as 'Business' or 'Personal'",
            "3. The 'Monthly Summary' sheet will automatically calculate totals",
            "4. This 'Tax Summary' sheet shows your reimbursable amounts",
            "5. Keep all Uber receipts as backup documentation",
            "6. Print or save this summary for tax filing",
            "",
            "TIP: For business trips, include purpose and client/meeting details"
        ]

        for i, instruction in enumerate(instructions, 15):
            tax_ws.cell(row=i, column=1, value=instruction)

        # Format currency in tax summary
        for row in tax_ws.iter_rows(min_row=8, max_row=14, min_col=2, max_col=2):
            for cell in row:
                if isinstance(cell.value, (int, float)) and cell.value != '':
                    cell.number_format = '$#,##0.00'

    return filename


def main():
    """Main function to create the template"""
    try:
        filename = create_uber_tax_template()
        print(f"✅ Success! Created: {filename}")
        print("\n📋 Template Features:")
        print("• Main expense tracking with automatic calculations")
        print("• Monthly summary with trip counts and totals")
        print("• Tax summary with reimbursable amounts")
        print("• Business/Personal categorization")
        print("• Sample data to get you started")
        print("• Ready-to-use Excel format")
        print("\n💡 Simply replace the sample data with your actual Uber trips!")
        print("📍 File saved in current directory")

        return filename

    except Exception as e:
        print(f"❌ Error creating template: {e}")
        import traceback
        print(traceback.format_exc())
        return None


if __name__ == "__main__":
    main()
