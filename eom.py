import pandas
from date_ranges import DateRange
import locale
import glob
import pprint
locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')

class EOM(DateRange):
  def __init__(self, year, month, EOM_month_dir, exp_acct_info, depo_acct_info):
    self.year = year
    self.month = month
    self.month_dir = EOM_month_dir
    self.exp_acct_info = exp_acct_info
    self.depo_acct_info = depo_acct_info

    # Mapping bank acct csv category names to that used in personal finance tracker.
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

  def dollarStr_to_float(self, modified_dataframe, amount_col):
    """
    Convert dollar amount from string to float if needed.
    :param modified_dataframe: A dataframe filtered for data from a particular month.
    :param date_col:
    :return: modified_dataframe.
    """
    for index, row in modified_dataframe.iterrows():
      if pandas.isna(row[amount_col]):
        pass
      else:
        amount_is_str = isinstance(row[amount_col], str)
        break

    if amount_is_str:
      for index, row in modified_dataframe.iterrows():
        try:
          modified_dataframe.at[index, amount_col] = 0 - locale.atof(row[amount_col][1:])
          # When "$" is used, Expense is often shown as positive in bank data. Thus making it negative so that it matches the format/pattern of other bank data.
        except TypeError:  # When the cell is blank (NaN).
          modified_dataframe.at[index, amount_col] = 0.0
    return modified_dataframe

  def modify_df(self, df, date_col, amount_col):
    """
    Filter df by date then convert dollar amount from str to float.
    :param df: A df is generated by reading a csv file of bank transactions.
    :param date_col:
    :param amount_col:
    :return: modified_df.
    """
    m_date = DateRange(self.year, self.month)
    modified_df = df[(df[date_col] > m_date.month_begin) & (df[date_col] < m_date.month_end)]
    # # To apply a filter on dataframe, use date from date_col (date column). Rows with dates bigger than month
    # beginning date AND smaller than month ending date are extracted. (A bank csv file often contains data from
    # multiple months, since billing cycles often span across months, so we need to filter out data of a particular month.)
    # TODO: rewrite date_range.
    modified_df = self.dollarStr_to_float(modified_df, amount_col)
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
      elif key in self.category_ref: # Modify category names (change them to standardized ones).
        self.summary[transaction_type][self.category_ref[key]] += value
      elif transaction_type == "Expenses":
        self.summary[transaction_type]["Discretionary"] += value

  def get_total(self, transaction_dict, transaction_type):
    """
    Calculate total expenses or deposits from one bank account.
    :param transaction_dict:
    :param transaction_type:
    :return: a list. for one account, including info on expenses or deposits, and total. This will be printed in the end for easy viewing.
    """
    total = sum(transaction_dict.values())
    res = [transaction_dict, {f"Total_{transaction_type}": total}]
    return res

  def tally_exp_accts(self):
    """
    Calculate expenses (in different categories) of each bank account.
    :param self
    :return: None.
    """
    for acct, info in self.exp_acct_info.items():
      date_col, category_col, amount_col, description_col = info["acct_col"]
      expenses = {}
      for f_name in glob.glob(f"{self.month_dir}/Expenses/{acct}/*"):
        df = pandas.read_csv(f_name)
        modified_df = self.modify_df(df, date_col, amount_col)
        # Filter out the actual expenses (excluding internal transfers etc).
        num_filtered = modified_df[(modified_df[amount_col] < 0) & (modified_df[category_col] != "Transfers") & (modified_df[category_col] != "Credit Card Payments")]

        # Tally numbers for each category.
        for (index, row) in num_filtered.iterrows():
          if "AMZN" in row[description_col]:
            this_category = "Amazon"
          elif "TARGET" in row[description_col]:
            this_category = "Target"
          elif "DOG STOP" in row[description_col] or "CHEWY" in row[description_col]:
            this_category = "Pets"
          else:
            this_category = row[category_col]

          expenses.setdefault(this_category, 0)
          expenses[this_category] -= row[amount_col]

      self.add_to_summary(expenses, "Expenses")
      self.exp_acct_info[acct]["Expenses"] = self.get_total(expenses, "Expenses")

  def tally_depo_accts(self):
    """
    Calculate deposits (in different categories) of each bank account.
    :param self
    :return: None.
    """
    for acct, info in self.depo_acct_info.items():
      date_col, category_col, amount_col, description_col = info["acct_col"]
      deposits = {}
      for f_name in glob.glob(f"{self.month_dir}/Deposits/{acct}/*"):
        df = pandas.read_csv(f_name)
        modified_df = self.modify_df(df, date_col, amount_col)
        # Filter out the actual deposits (excluding internal transfers etc).
        num_filtered = modified_df[(modified_df[category_col] == "Paychecks") | (modified_df[category_col] == "Interest")]

        # Tally numbers for each category.
        for (index, row) in num_filtered.iterrows():
          this_category = row[category_col]
          deposits[this_category] = deposits.setdefault(this_category, 0) - row[amount_col]

      self.add_to_summary(deposits, "Deposits")
      self.depo_acct_info[acct]["Deposits"] = self.get_total(deposits, "Deposits")

  def round_num(self, acct_l):
    return [{k: round(v, 2) for k, v in d.items()} for d in acct_l]

  def print_acct_details(self):
    pp = pprint.PrettyPrinter(indent=2)
    print("Summary")
    self.summary = {k: self.round_num(v) for k, v in self.summary.items()}
    pp.pprint(self.summary)

    print("\nAccount Details")
    print("- Deposits")
    for acct, info in self.depo_acct_info.items():
      info['Deposits'] = self.round_num(info["Deposits"])
      print(f"{acct}:")
      pp.pprint(info['Deposits'])
    print("\n- Expenses")
    for acct, info in self.exp_acct_info.items():
      info["Expenses"] = self.round_num(info["Expenses"])
      print(f"{acct}: ")
      pp.pprint(info['Expenses'])