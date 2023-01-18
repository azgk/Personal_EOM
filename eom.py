import pandas
from date_ranges import DateRange
import locale
import glob
import pprint
locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')


class EndOfMonthFinance:
  def __init__(self, year=2023, month=1, EOM_month_dir="csv_files", acct_info={"acct": "acct info"}):
    self.year = year
    self.month = month
    self.month_dir = EOM_month_dir
    self.acct_info = acct_info

    # Mapping category names in .csv to those chosen for this project.
    self.category_ref = {
      "Healthcare": "Discretionary",
      "Health & Wellness": "Discretionary",
      "Auto + Gas": "Transportation",
      "Other Expenses": "Discretionary",
      "Travel": "Discretionary",
      "Bills & Utilities": "Utilities",
      "Food & Drink": "Restaurants",
      "Automotive": "Transportation",
      "Gas": "Transportation",
      "Misc": "Discretionary",
      "Cable + Phone": "Utilities",
      "Services + Supplies": "Utilities",
      "Personal + Family": "Rent",
    }

    self.summary = {
      "Deposits": {
        "Paychecks": 0,
        "Interest": 0,
        "Return": 0,
        "Miscellaneous": 0,
      },
      "Expenses": {
        "Groceries": 0,
        "Restaurants": 0,
        "Amazon": 0,
        "Target": 0,
        "Transportation": 0,
        "Utilities": 0,
        "Entertainment": 0,
        "Pets": 0,
        "Discretionary": 0,
        "Rent": 0
      }
    }

  def convert_dollarStr(self, month_df, amount_col, uncommon_col):
    """
    Convert dollar amount from string to float if needed.
    :param month_df: A Pandas DataFrame (df) filtered for data from a particular month.
    :param amount_col: The header of dollar amount column in df.
    :param uncommon_col: A second column (if any) for dollar amount.
    :return: month_df: A modified month_df.
    """
    # Check if type of dollar amount is string.
    for index, row in month_df.iterrows():
      if pandas.isna(row[amount_col]):
        pass
      else:
        amount_is_str = isinstance(row[amount_col], str)
        break

    # Convert string to float.
    if amount_is_str:
      if uncommon_col is None:
        for index, row in month_df.iterrows():
          try:
            month_df.at[index, amount_col] = 0 - locale.atof(row[amount_col][1:])
          # Whenever "$" is used, Expense is often shown as positive in bank data. Thus making it negative so that it
          # matches the format/pattern of other bank data.
          except TypeError:  # When the cell is blank (NaN).
            pass
      else:
        for index, row in month_df.iterrows():
          if pandas.isna(row[amount_col]):
            month_df.at[index, uncommon_col] = locale.atof(row[uncommon_col][1:])
          else:
            month_df.at[index, amount_col] = 0 - locale.atof(row[amount_col][1:])

    return month_df

  def modify_df(self, df, date_col, amount_col, acct):
    """
    Filter df by date then convert dollar amount from str to float.
    :param df: A df generated by reading a .csv file of bank transactions.
    :param date_col: The header of date column in df.
    :param amount_col: The header of dollar amount column in df.
    :param acct: The bank account name.
    :return: modified_df.
    """
    date_range = DateRange(self.year, self.month)
    month_begin, next_month_begin = date_range.month_begin, date_range.next_month_begin
    month_df = df[(df[date_col] >= month_begin) & (df[date_col] < next_month_begin)]
    # The dataframe is filtered by date--rows with dates bigger than or equal to 1st date of the month AND dates
    # smaller than 1st date of the next month are extracted. (A .csv often contains data from multiple months,
    # since billing cycles often span across months. Thus the need for filtering.)

    self.acct_info[acct].setdefault("uncommon_col", None)  # Exception: when there is a second column for dollar
    # amount # in .csv the second column also needs to have dollar strings converted to integers.
    modified_df = self.convert_dollarStr(month_df, amount_col, self.acct_info[acct]["uncommon_col"])
    return modified_df

  def add_to_summary(self, transaction_dict, transaction_type):
    """
    Tally up everything to self.summary.
    :param transaction_dict: a dict of expenses or a dict of deposits.
    :param transaction_type: a string. "Expenses" or "Deposits".
    :return: None.
    """
    for key, value in transaction_dict.items():
      if key in self.summary[transaction_type]:
        self.summary[transaction_type][key] += value
      elif key in self.category_ref:  # Modify category names (change them to standardized ones).
        new_key = self.category_ref[key]
        self.summary[transaction_type].setdefault(new_key, 0)
        self.summary[transaction_type][new_key] += value
      elif transaction_type == "Expenses":
        self.summary[transaction_type]["Discretionary"] += value
      elif transaction_type == "Deposits":
          self.summary[transaction_type]["Miscellaneous"] += value

  def get_total(self, transaction_dict):
    """
    Calculate total expenses or deposits from one bank account.
    """
    total = sum(transaction_dict.values())
    return total

  def read_keywords(self, row, description_col, category_col):
    """
    Rename categories based on keywords in transaction description.
    """
    keywords_to_category = {
      "VENMO": "Discretionary",
      "AMZN": "Amazon",
      "TARGET": "Target",
      "DOG STOP": "Pets",
      "CHEWY": "Pets",
      "CREDIT CARD PMT": None,
      "AUTOMATIC PAYMENT": None,
    }
    for keyword, standard_category in keywords_to_category.items():
      if keyword in row[description_col]:
        this_category = standard_category
        break
    else:
      this_category = row[category_col]
      if this_category == "Transfers" or this_category == "Credit Card Payments":
        this_category = None
    return this_category

  def tally_one_acct(self, acct, acct_cols):
    """
    Calculate expenses/deposits from one bank account.
    :param acct: Account name.
    :param acct_cols: Headers of columns in .csv files.
    :return: acct_expenses(dict) and acct_deposits (dict)
    """
    # Modify csv data (filter by date, convert dollar amount from string to float)
    date_col, category_col, amount_col, description_col = acct_cols
    acct_expenses, acct_deposits = {}, {}
    for f_name in glob.glob(f"{self.month_dir}/{acct}/*"):
      df = pandas.read_csv(f_name)
      modified_df = self.modify_df(df, date_col, amount_col, acct)

      # Determine category then tally numbers for each category.
      for (index, row) in modified_df.iterrows():
        this_category = self.read_keywords(row, description_col, category_col)
        if this_category is not None:  # The tally does not include rows for internal transfers (e.g. credit card
          # payments).
          if row[amount_col] < 0:  # For expenses (negative float).
            acct_expenses[this_category] = acct_expenses.setdefault(this_category, 0) + row[amount_col]
          elif row[amount_col] > 0:  # For credit card refund etc (positive float).
            acct_deposits[this_category] = acct_deposits.setdefault(this_category, 0) + row[amount_col]
          elif pandas.isna(row[amount_col]):  # Exception: PNC csv has one column for withdrawals and another for
            # deposits. For each row, one of these two columns is empty.
            uncommon_amount_col = self.acct_info[acct]["uncommon_col"]
            acct_deposits[this_category] = acct_deposits.setdefault(this_category, 0) + row[uncommon_amount_col]
    return acct_expenses, acct_deposits

  def tally_all_accts(self):
    """
    Calculate total expenses and total deposits from all bank accounts.
    :param self
    :return: None.
    """
    for acct, info in self.acct_info.items():
      acct_expenses, acct_deposits = self.tally_one_acct(acct, info["acct_cols"])
      self.add_to_summary(acct_expenses, "Expenses")
      self.acct_info[acct]["Expenses"] = [acct_expenses, {"Total": self.get_total(acct_expenses)}]
      self.add_to_summary(acct_deposits, "Deposits")
      self.acct_info[acct]["Deposits"] = [acct_deposits, {"Total": self.get_total(acct_deposits)}]

  def print_acct_details(self):
    pp = pprint.PrettyPrinter(indent=2)
    print("Summary: ")
    self.summary = {k: [v] for k, v in self.summary.items()}
    self.summary["Deposits"].append({"Total": self.get_total(self.summary["Deposits"][0])})
    self.summary["Expenses"].append({"Total": self.get_total(self.summary["Expenses"][0])})
    pp.pprint(self.summary)

    print("\nAccount Details\n")
    for acct, info in self.acct_info.items():
      for type in ("Deposits", "Expenses"):
        print(f"{acct}_{type}:")
        pp.pprint(info[f"{type}"])
      print("\n")
