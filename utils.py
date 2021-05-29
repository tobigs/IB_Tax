from os import name
import pandas as pd

from collections import namedtuple

from currency_converter import CurrencyConverter
c = CurrencyConverter(fallback_on_missing_rate=True)


def addSumCol(df):
    df.loc[:,'Sum'] = df.sum(numeric_only=True, axis=1)
    return df

def addSumRow(df):
    if isinstance(df.index, pd.MultiIndex):
        myRange = range(df.index.nlevels)
        myIndex = tuple('Sum' for x in myRange)
        df.loc[myIndex,:]= df.sum(numeric_only=True, axis=0)
    else:
        df.loc['Sum']= df.sum(numeric_only=True, axis=0)
    return df

def parse_activityStatement(myFile):
    # https://stackoverflow.com/questions/27020216/import-csv-with-different-number-of-columns-per-row-using-pandas/57824142#57824142
    ### Loop the data lines
    with open(myFile, 'r') as temp_f:
        # get No of columns in each line
        col_count = [ len(l.split(",")) for l in temp_f.readlines() ]

    ### Generate column names  (names will be 0, 1, 2, ..., maximum columns - 1)
    column_names = [i for i in range(0, max(col_count))]

    ### Read csv
    df = pd.read_csv(myFile, header=None, delimiter=",", names=column_names)

    return df

def get_trades(df):
    df_trades = df[df.iloc[:,0] == "Trades"].dropna(how='all', axis=1)
    df_trades, df_trades.columns = df_trades.iloc[1:] , df_trades.iloc[0]
    df_trades.columns.name = None

    # obtain asset type
    try:
        df_trades[['Asset','Category']] = df_trades["Asset Category"].str.split("-", expand=True).copy()
    except:
        df_trades["Asset"] = df_trades["Asset Category"]

    # remove subheader
    df_trades = df_trades[(df_trades["Realized P/L"]!="Realized P/L") & ~(df_trades["Header"].str.contains("SubTotal|Total"))].copy()

    # convert dtypes
    df_trades["Realized P/L"] = df_trades["Realized P/L"].astype(float)

    # remove empty rows
    df_trades = df_trades[df_trades["Realized P/L"].notnull()] #df_trades["Realized P/L"]!=0) &
    
    # convert to datetime
    df_trades["Date/Time"] = pd.to_datetime(df_trades["Date/Time"],  infer_datetime_format=True)

    df_futures = df_trades[df_trades["Asset Category"].str.contains("Futures")]     if df_trades["Asset Category"].str.contains("Futures").sum() > 0 else pd.DataFrame()
    df_options = df_trades[df_trades["Asset Category"].str.contains("Options")]     if df_trades["Asset Category"].str.contains("Options").sum() > 0 else pd.DataFrame()
    df_cfd = df_trades[df_trades["Asset Category"].str.contains("CFD")]     if df_trades["Asset Category"].str.contains("CFD").sum() > 0 else pd.DataFrame()

    df_trades = df_trades.reset_index(drop=True)

    # convert to EUR using ECB rates
    df_trades["P/L [€]"] = df_trades.apply(lambda row: c.convert(
        row["Realized P/L"] , row.Currency, date=row["Date/Time"]), axis=1)
    df_trades["P [€]"] = df_trades["P/L [€]"].apply(lambda row: row if row > 0 else 0)
    df_trades["L [€]"] = df_trades["P/L [€]"].apply(lambda row: row if row < 0 else 0)

    PL_TradesDet = df_trades.groupby(["Currency", "Asset"]).sum()
    PL_Trades = df_trades.groupby(["Asset"]).sum()

    trades = namedtuple('trades', ['pl', 'plDet', 'trades', 'futures', 'options', 'cfd'])

    return trades(PL_Trades, PL_TradesDet, df_trades, df_futures, df_options, df_cfd)

def get_dividends(df):

    def _process_df(df):
        # set first row as header
        df, df.columns = df.iloc[1:] , df.iloc[0]
        
        # remove rows with sum
        df = df[~df.Currency.str.contains("Total")]
        
        # convert dtypes
        df["Amount"] = df["Amount"].astype(float)
        
        # convert to datetime
        df["Date"] = pd.to_datetime(df["Date"],  infer_datetime_format=True)
        
        # convert to EUR using ECB rates
        df["Amount [€]"] = df.apply(lambda row: c.convert(row["Amount"] , row["Currency"], date=row["Date"]), axis=1)
        
        # label CFD dividens
        df["Description"] = df["Description"].str.replace(" ","")
        df[['Symbol','TrashCol']] = df["Description"].str.split("(", n=1, expand=True).copy()
        df[['Country','TrashCol']] = df["TrashCol"].str.split(")", n=1, expand=True).copy()
        df["Country"] = df["Country"].str.extract(r'(^\D+)').fillna("CFD")
        df["Asset"] = "Stocks"
        df.loc[df.Symbol.str.endswith("n"), "Asset"] = "CFDs" 
        
        # remove index from column names
        df.columns.name = None
        df.reset_index(drop=True)
        
        return df

    df_div = df[df.iloc[:,0] == "Dividends"].dropna(how='all', axis=1)
    df_wtax = df[df.iloc[:,0] == "Withholding Tax"].dropna(how='all', axis=1)
    df_871 = df[df.iloc[:,0] == "871(m) Withholding"].dropna(how='all', axis=1)

    df_div = _process_df(df_div)
    df_wtax = _process_df(df_wtax) if not df_wtax.empty else df_wtax

    df_871 = _process_df(df_871) if not df_871.empty else df_871
    df_871["Asset"] = "CFDs"
    df_wtax = df_wtax.append(df_871)

    WithholdingTax = df_wtax.groupby(["Currency", "Asset", "Country"]).sum() if not df_wtax.empty else df_wtax
    Dividends = df_div.groupby(["Currency", "Asset", "Country"]).sum()

    return WithholdingTax, Dividends

def get_interest(df):
    # reduce df & convert dtypes
    df_interest = df[df.iloc[:,0] == "Interest"].dropna(how='all', axis=1)
    df_interest, df_interest.columns = df_interest.iloc[1:] , df_interest.iloc[0]
    df_interest = df_interest[~df_interest["Currency"].str.contains("SubTotal|Total")]
    df_interest["Amount"] = df_interest["Amount"].astype(float)

    # convert to datetime
    df_interest["Date"] = pd.to_datetime(df_interest["Date"],  infer_datetime_format=True)
    # convert to EUR using ECB rates
    df_interest["Amount [€]"] = df_interest.apply(lambda row: c.convert(row["Amount"] , row["Currency"], date=row["Date"]), axis=1)
    df_interest.columns.name = None

    # aggregate positive and negative
    Interest = df_interest.groupby(["Currency"])[['Amount','Amount [€]']].agg([
        ("Received", lambda x: x[x>0].sum()),
        ("Paid", lambda x: x[x<0].sum())
    ])

    return Interest

def getTradesPnl(df, multiplier):
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()
    else:
        try:
            df["TPrice"] = df["T. Price"].astype(float) * multiplier
            df["TPrice"] = df["TPrice"] * -df["Quantity"].astype(int)
            df["TPrice"] = df["TPrice"] + df["Comm/Fee"].astype(float) 
            df["Pnl"] = df.apply(lambda row: c.convert(
                        row["TPrice"] , row.Currency, date=row["Date/Time"]), axis=1)
            df["cummulative"] = df["Pnl"].cumsum()

            df["Open"] = df.Code.str.match(r'(C)(?!\w)') # regex should also include (O) not prepended with word char
            df["Open"] = df["Open"].cumsum().shift().fillna(0)

            s1 = df.groupby("Open").last()["Symbol"]
            s2 = df.groupby("Open").sum()["Pnl"]
        except:
            s1 = pd.Series([0], name="Symbol")
            s2 = pd.Series([0], name="Pnl")

        df_resultDet = pd.concat([s1, s2], axis=1)
        df_result = pd.DataFrame()

        try:
            df_result["P [€]"] = [df_resultDet["Pnl"].apply(lambda row: row if row > 0 else 0).sum()]
            df_result["L [€]"] = [df_resultDet["Pnl"].apply(lambda row: row if row < 0 else 0).sum()]
        except:
            pass

        return df_result, df_resultDet

def get_kap(activityStatement, includeCfd=False):

    # unpack namedTuple
    PL_Trades = activityStatement.pl
    PL_TradesDet = activityStatement.plDet
    Options = activityStatement.options
    OptionsDet = activityStatement.optionsDet
    Dividends = activityStatement.dividends
    Interest = activityStatement.interest

    # identify category strings
    optStr, stockStr, cfdStr, futStr = "", "", "", ""
    if PL_Trades.index.str.contains("Option").sum() > 0:
        optStr = PL_Trades.index[PL_Trades.index.str.contains("Option")][0]
    if PL_Trades.index.str.contains("Stock").sum() > 0:
        stockStr = PL_Trades.index[PL_Trades.index.str.contains("Stock")][0]
    if PL_Trades.index.str.contains("CFD").sum() > 0:
        cfdStr = PL_Trades.index[PL_Trades.index.str.contains("CFD")][0]
    if PL_Trades.index.str.contains("Futures").sum() > 0:
        futStr = PL_Trades.index[PL_Trades.index.str.contains("Futures")][0]

    lst_kap = []

    #################################
    # Line 18 German capital income, Interest + option premium
    # according to pwc report without dividend ger
    #region##########################

    dividendGer = Dividends[Dividends.index.get_level_values(2) == 'DE'].sum()["Amount [€]"]
    interest = Interest.sum()["Amount [€]"]["Received"]
    #TODO: only german, instead of current only eur
    optPremEur = PL_TradesDet["P [€]"]["EUR"][optStr]     if optStr in PL_TradesDet["P [€]"]["EUR"].index     else 0

    if OptionsDet.empty:
        optPremEur = 0
    else:
        try:
            # hard coded, german stocks selected
            gerStock = "FRE|SAP"
            gerStockMask = OptionsDet.Symbol.str.contains(gerStock)
            optPremEur = OptionsDet[gerStockMask]["Pnl"].sum()
        except:
            # if first 3 options trades are german
            optPremEur = OptionsDet[:3]["Pnl"].sum()
            
    capIncomeGer = interest + optPremEur

    # deprecated
    mask = (PL_TradesDet["P [€]"].index.get_level_values(0) != "EUR") & (PL_TradesDet["P [€]"].index.get_level_values(1) == optStr)
    optPrem = PL_TradesDet["P [€]"][mask].sum()
    # new
    optPrem = Options["P [€]"].sum() - optPremEur if not Options.empty else 0

    #endregion#######################
    # Line 20, Line 23 Stock Profit & Loss
    #region##########################

    stockProfit = PL_Trades["P [€]"][stockStr] if stockStr in PL_Trades["P [€]"].index else 0
    stockLoss = PL_Trades["L [€]"][stockStr] if stockStr in PL_Trades["L [€]"].index else 0

    #endregion#######################
    # Line 22 non Stock loss (future loss + option loss)
    #region##########################

    # nonStockLoss = PL_Trades["L [€]"][(PL_Trades["L [€]"].index != stockStr) & (PL_Trades["L [€]"].index != cfdStr)].sum()
    nonStockLoss = PL_Trades["L [€]"][futStr] if futStr in PL_Trades["L [€]"].index else 0
    nonStockLoss = nonStockLoss + Options["L [€]"].sum() if not Options.empty else 0 

    #endregion#######################
    # Line 19 Foreign capital income
    #region##########################
    # stock profit + other loss + stock loss + option premium + dividend - line18
    capIncome = stockProfit + nonStockLoss + stockLoss + optPrem + Dividends.sum()["Amount [€]"] - dividendGer

    # cfd
    if includeCfd:
        cfdLoss = PL_TradesDet[PL_TradesDet.index.get_level_values(1) == cfdStr]["L [€]"].sum()
        cfdProfit = PL_TradesDet[PL_TradesDet.index.get_level_values(1) == cfdStr]["P [€]"].sum()
        cfdDividend = Dividends[Dividends.index.get_level_values(1) == cfdStr]["Amount [€]"].sum()
        
        nonStockLoss = nonStockLoss + cfdLoss
        capIncome = capIncome + cfdProfit + cfdDividend

    lst_kap.append(["Line 18", capIncomeGer])
    lst_kap.append(["Line 19", capIncome])
    lst_kap.append(["Line 20", stockProfit])
    lst_kap.append(["Line 22", nonStockLoss])
    lst_kap.append(["Line 23", stockLoss])

    KAP = pd.DataFrame(lst_kap, columns=["Name","Value"])

    return KAP
        
