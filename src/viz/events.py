"""Dated market events used to annotate the long-run price and ratio charts.

Each entry is anchored on a turning point visible in the published series and states what the
sources read say happened around that date. They are coincidences in time, documented by the
sources listed; none of them is a causal estimate made by this project."""
from __future__ import annotations

BIS = ("Chan, Ng and Ramchand, BIS Papers No 64 (2012)", "https://www.bis.org/publ/bppdf/bispap64h.pdf")
SG1997 = ("Singapore Government press release, 18 Nov 1997", "https://nas.gov.sg/archivesonline/data/pdfdoc/1997111804.htm")
SG101 = ("SG101, The 1985 Recession", "https://www.sg101.gov.sg/economy/case-studies/1985/")
STACKED_CRASH = ("Stacked Homes, past price falls (secondary source)",
                 "https://stackedhomes.com/should-you-wait-for-the-property-market-to-dip-heres-what-past-price-crashes-in-singapore-show")
STACKED_COOL = ("Stacked Homes, cooling measures since 2009 (secondary source)", "https://stackedhomes.com/singapore-cooling-measures-history/")
PROPNEX = ("PropNex, 23 Oct 2015 (secondary source)", "https://www.propnex.com/news-details/2833/public-home-prices-continue-to-fall-in-q3")
IREUS = ("NUS IREUS study as reported in 2022 (secondary source)",
         "https://condosingapore.com/showthread.php/34690-Shocks-to-property-sector-usually-stretch-beyond-the-recessions-IREUS")
REVUE_BANQUE = ("Revue Banque, 2005", "https://www.revue-banque.fr/binrepository/0000000000000000000_BRB01730_MG108003131.pdf")
CEPII = ("Grjebine, CEPII, L'économie mondiale 2014", "https://imap.cepii.fr/PDF_PUB/em/2014/em2014-04.pdf")
NOT_2012 = ("Notaires de Paris-Île-de-France, press release 23 Feb 2012", "https://www.dalloz-actualite.fr/document/communique-de-presse-23-fevr-2012")
NOT_PV = ("Notaires de Paris-Île-de-France, market at end February 2012",
          "https://paris.notaires.fr/fr/actualites/immobilier-paris-et-en-ile-de-france-le-mouvement-de-baisse-des-prix-se-poursuit")
FNAIM = ("FNAIM, press release 3 Jan 2012", "https://www.dalloz-actualite.fr/document/communique-de-presse-fnaim-3-janv-2012")
NOT_2023 = ("Notaires du Grand Paris, press conference 7 Sept 2023, as reported (secondary source)",
            "https://www.empruntis.com/financement/actualites/2023/crise-immobiliere-chute-prix-devrait-atteindre-5-5-octobre-2023-16213/")

# kind: "crisis" (financial or economic crisis), "policy" (tax or lending rule), "rates" (interest rates),
# "boom" (end of a boom described as speculative by the sources), "none" (no cause verified)
EVENTS = {
    "paris": [
        ("1992Q1", "boom", "End of the 1985–1991 boom",
         "The index starts inside the fall that followed the 1985–1991 boom in Île-de-France, which the sources describe "
         "as a speculative bubble. Real prices in Paris fell by nearly 46% between 1991 and 1997.", [REVUE_BANQUE, CEPII]),
        ("2008Q3", "crisis", "Global financial crisis",
         "First peak of the cycle in 2008 Q3, followed by a short fall during the global financial crisis; prices were "
         "rising again by the end of 2009.", [NOT_2012]),
        ("2011Q3", "policy", "Euro-area debt crisis, tighter credit, capital-gains tax reform",
         "Both ratios peak, then prices move sideways until 2012 Q3 and drift down. Lenders tightened conditions during "
         "the sovereign debt crisis, and the capital-gains tax reform of 1 February 2012 pulled sales forward into "
         "January 2012, after which volumes dropped.", [FNAIM, NOT_PV]),
        ("2020Q3", "rates", "Peak, then the rise in interest rates from 2022",
         "Highest level of the index and of both ratios. The notaries attribute the fall in sales and prices to the rise "
         "in mortgage rates since early 2022 and the loss of borrowing capacity. The first part of the fall, in 2020–2021, "
         "has no verified cause in the sources read.", [NOT_2023]),
    ],
    "singapore_private": [
        ("1981Q2", "policy", "Pension savings opened to private purchases, then the 1985 recession",
         "Peak after the 1981 scheme that let buyers use their Central Provident Fund savings for private homes; the fall "
         "lasted until 1986 and spans Singapore's first recession (1985), marked by a construction slump.",
         [STACKED_CRASH, SG101]),
        ("1996Q2", "crisis", "Anti-speculation package, then the Asian financial crisis",
         "Prices had more than doubled between 1990 and 1996. The government announced anti-speculation measures on "
         "14 May 1996; the Asian financial crisis from mid-1997 deepened the fall, and the index bottomed in 1998 Q4, "
         "45% below its peak.", [BIS, SG1997]),
        ("2000Q2", "crisis", "Dot-com bust and 2001 recession",
         "The decline from 2000 Q3 coincides with the end of the dot-com boom and was prolonged by the 2001 recession, "
         "the SARS outbreak and the second Gulf War.", [IREUS]),
        ("2008Q1", "crisis", "Global financial crisis",
         "The index lost about a quarter of its value, then rebounded quickly in 2009 as interest rates fell.", [BIS]),
        ("2013Q3", "policy", "Cooling measures on stamp duty and lending",
         "Peak after successive rounds of measures: higher additional buyer's stamp duty in January 2013 and a cap on "
         "total debt service introduced in June 2013. Prices then slid for about four years.", [STACKED_COOL, PROPNEX]),
        ("2021Q1", "none", "Price-to-rent peak; no cause verified",
         "Highest price-to-rent ratio of the series. In the following quarters the official rent index rose faster than "
         "the price index, which brought the ratio back down. No source read attributes this to one cause.", []),
    ],
    "singapore": [
        ("1996Q4", "crisis", "Asian financial crisis, then the 2001 recession",
         "Peak of resale prices a few months before the Asian financial crisis (mid-1997); the index fell until 2002. "
         "No source specific to resale flats was read for this episode.", [BIS]),
        ("2013Q2", "policy", "Tighter lending rules for flats",
         "Peak of resale prices and of the price-to-income ratio (2011–2013). In January 2013 monthly repayments on bank "
         "loans for flats were capped at 30% of income, and the maximum loan term was cut in August 2013; resale prices "
         "then fell for nine consecutive quarters to 2015 Q3 and stayed lower until 2019.", [STACKED_COOL, PROPNEX]),
    ],
}

KIND = {"crisis": "Financial or economic crisis", "policy": "Tax or lending rule", "rates": "Interest rates",
        "boom": "End of a boom", "none": "No cause verified"}
