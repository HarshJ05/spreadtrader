"""The futures pairs this engine is allowed to trade.

Pairs are chosen *before* looking at any results, because there is an economic
reason for each pair's prices to move together. Picking pairs by searching all
combinations for the best backtest would be data mining.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Future:
    ticker: str      # Yahoo Finance continuous front-month symbol
    name: str
    group: str


FUTURES = {
    "CL=F": Future("CL=F", "WTI crude oil", "Energy"),
    "BZ=F": Future("BZ=F", "Brent crude oil", "Energy"),
    "HO=F": Future("HO=F", "Heating oil", "Energy"),
    "RB=F": Future("RB=F", "RBOB gasoline", "Energy"),
    "GC=F": Future("GC=F", "Gold", "Metals"),
    "SI=F": Future("SI=F", "Silver", "Metals"),
    "PL=F": Future("PL=F", "Platinum", "Metals"),
    "ZT=F": Future("ZT=F", "US 2-year Treasury note", "Rates"),
    "ZF=F": Future("ZF=F", "US 5-year Treasury note", "Rates"),
    "ZN=F": Future("ZN=F", "US 10-year Treasury note", "Rates"),
    "ZB=F": Future("ZB=F", "US 30-year Treasury bond", "Rates"),
    "ES=F": Future("ES=F", "S&P 500 E-mini", "Equity index"),
    "NQ=F": Future("NQ=F", "Nasdaq-100 E-mini", "Equity index"),
    "YM=F": Future("YM=F", "Dow Jones E-mini", "Equity index"),
    "ZC=F": Future("ZC=F", "Corn", "Agriculture"),
    "ZW=F": Future("ZW=F", "Wheat", "Agriculture"),
    "ZS=F": Future("ZS=F", "Soybeans", "Agriculture"),
    "ZM=F": Future("ZM=F", "Soybean meal", "Agriculture"),
}


@dataclass(frozen=True)
class Pair:
    y: str           # leg we buy when the spread is cheap
    x: str           # leg we hedge with
    why: str         # the economic link

    @property
    def id(self) -> str:
        return f"{self.y.replace('=F', '')}-{self.x.replace('=F', '')}"

    @property
    def label(self) -> str:
        return f"{FUTURES[self.y].name} vs {FUTURES[self.x].name}"


PAIRS = [
    Pair("CL=F", "BZ=F", "Two crude oil benchmarks; the gap reflects transport and quality differences."),
    Pair("HO=F", "RB=F", "Both are refined from crude oil; refiners switch output between them."),
    Pair("GC=F", "SI=F", "Precious metals driven by real interest rates and the dollar."),
    Pair("GC=F", "PL=F", "Precious metals; platinum also has industrial demand."),
    Pair("ZF=F", "ZN=F", "Neighbouring points on the US Treasury yield curve."),
    Pair("ZT=F", "ZF=F", "Short end of the US Treasury yield curve."),
    Pair("ZN=F", "ZB=F", "Long end of the US Treasury yield curve."),
    Pair("ES=F", "YM=F", "Two US large-cap stock indices with overlapping members."),
    Pair("ES=F", "NQ=F", "US large caps vs tech-heavy Nasdaq-100."),
    Pair("ZS=F", "ZM=F", "Soybeans are crushed into soybean meal (the 'crush' spread)."),
    Pair("ZC=F", "ZW=F", "Feed grains that substitute for each other."),
]

TICKERS = sorted({p.y for p in PAIRS} | {p.x for p in PAIRS})
