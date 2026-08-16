# Recommended References

最初は以下だけ読めば十分です。

## 1. 最重要: 原論文

**Moskowitz, Ooi, Pedersen (2012), “Time Series Momentum”, Journal of Financial Economics 104(2), 228–250.**

- Time-Series Momentumの定義と代表的検証。
- 58の株価指数・通貨・商品・債券先物/forward。
- 過去12か月returnと将来returnの関係が中心。

URL:
https://www.sciencedirect.com/science/article/pii/S0304405X11002613

AQR summary:
https://www.aqr.com/Insights/Research/Journal-Article/Time-Series-Momentum

## 2. 原論文データ

**AQR — Time Series Momentum: Original Paper Data**

https://www.aqr.com/Insights/Datasets/Time-Series-Momentum-Original-Paper-Data

**AQR — Time Series Momentum: Factors, Monthly（更新系列）**

https://www.aqr.com/Insights/Datasets/Time-Series-Momentum-Factors-Monthly

**Tobias Moskowitz / Yale — Data**

https://faculty.som.yale.edu/tobymoskowitz/research/data/

実装結果のsanity checkや、原研究のreturn series確認に有用。

## 3. 長期証拠

**Hurst, Ooi, Pedersen — A Century of Evidence on Trend-Following Investing**

https://www.aqr.com/insights/research/journal-article/a-century-of-evidence-on-trend-following-investing

1880年まで遡り、trend followingが短期間の偶然かを検討。

## 4. OOS / 市場拡張

**Babu et al. — Trends Everywhere**

https://www.aqr.com/Insights/Research/Journal-Article/Trends-Everywhere

元論文で使っていない市場へ拡張したout-of-sample evidence。

## 5. 実運用イメージ

**Hurst, Ooi, Pedersen — Demystifying Managed Futures**

https://www.aqr.com/insights/research/journal-article/demystifying-managed-futures

Managed Futures/CTAのreturnがsimple trend-following/TSMOMでかなり説明できるという整理。

**Man AHL Explains — Momentum**

https://www.man.com/insights/ahl-explains-momentum

trend-following運用側からの短い概説。

## 6. 反証・批判も読む

**Huang et al. (2020), “Time series momentum: Is it there?”, Journal of Financial Economics.**

https://doi.org/10.1016/j.jfineco.2019.08.004

asset-by-assetのpredictabilityは弱いとする重要な批判。TSMOMを「証明済みの魔法」と扱わないために必読。

## 読む順番

1. AQR Time Series Momentum summary
2. 原論文 abstract / methodology
3. Original Paper Data
4. Demystifying Managed Futures
5. Century of Evidence
6. Trends Everywhere
7. “Is it there?” の反論

## 注意

AQR/Manの資料は研究・運用会社自身が公開しているものを含むため、肯定的な資料だけで結論を出さず、反証論文・自分のOOS検証とセットで使うこと。
