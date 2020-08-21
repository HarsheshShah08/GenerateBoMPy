import pandas as pd
import numpy as np


# import csv
# import os


def generatebom():
    """Read the files"""
    revitbom = "C:\\Users\\Harshesh\\OneDrive - Tophat\\Public\\BOM\\1\\1\\1_Revit.csv"
    hsbbom = "C:\\Users\\Harshesh\\OneDrive - Tophat\\Public\\BOM\\1\\1\\2_HSBCAD.csv"
    materialmaster = "C:\\Users\\Harshesh\\OneDrive - Tophat\\Public\\BOM\\1\\1\\MaterialMaster.csv"
    altuom = "C:\\Users\\Harshesh\\OneDrive - Tophat\\Public\\BOM\\1\\1\\AlternativeUoM.csv"
    #prevsapbom = np.nan
    prevsapbom = "C:\\Users\\Harshesh\\OneDrive - Tophat\\Public\\BOM\\1\\1\\sapbomdf1.csv"

    """create the dataframes"""
    rdf = pd.read_csv(revitbom)
    hsb_cols_to_use = ['Panel', 'Article', 'Qty', 'UOM']
    hdf = pd.read_csv(hsbbom, usecols=hsb_cols_to_use)
    mmdf = pd.read_csv(materialmaster)
    altuomdf = pd.read_csv(altuom)
    if prevsapbom is not np.nan:
        prevsapbomdf = pd.read_csv(prevsapbom)
        curritemid = prevsapbomdf['item_identifier'].max()+1
    else:
        prevsapbomdf = pd.DataFrame()
        curritemid = 10

    """create the back up of the dataframes"""
    # rdf.to_pickle("./revitbom_store.pkl")
    # hdf.to_pickle("./hsbbom_store.pkl")

    """clean material master & Alt material master"""
    cleanmaterialmaster(mmdf)
    cleanaltuom(altuomdf)

    """rename the columns to match with SAP BOM"""
    rdfrenamed = rdf.rename(columns={
        "Module": "Header Material", "ITEM NUMBER": "Component Material", '00 LM': 'Qty', })
    hdfrenamed = hdf.rename(
        columns={"Panel": "Header Material", "Article": "Component Material"})
    rdfrenamed["Source"] = "Revit"
    hdfrenamed["Source"] = "HSB"
    sdf = rdfrenamed.copy()
    sdf = sdf.append(hdfrenamed, ignore_index=True)
    sdf['valid_component'], sdf['valid_header'], sdf['valid_h_uom'], sdf['valid_c_uom'], sdf['discardbom'], sdf[
        'price'], sdf['item_identifier'] = [False, False, False, False, False, np.nan, np.nan]

    """Start creating the SAP BOM by iterating over each row of the design BOM"""
    for index, row in sdf.iterrows():
        tempheader = row['Header Material']
        tempcomp = row['Component Material']
        checkmaterial(sdf, mmdf, index)
        if len(sdf.loc[(sdf['Header Material'] == tempheader) & (sdf['Component Material'] == tempcomp)]) > 1:
            records = sdf.loc[(sdf['Header Material'] == tempheader) & (sdf['Component Material'] == tempcomp)].index
            if records[0] == index:
                for i in range(len(records)):
                    if i != 0:
                        if sdf.loc[records[0], 'UOM'] == sdf.loc[records[i], 'UOM'] \
                                and sdf.loc[records[i], 'discardbom'] == False:
                            sdf = addquantity(sdf, records[0], records[i])
                            print("Record has been added")
                        else:
                            print("we need to chnage the UOM to add")
        else:
            sdf.loc[index, 'discardbom'] = False
        """calculate the price of given bom"""
        if sdf.loc[index, 'valid_c_uom']:
            mmindex = mmdf.loc[mmdf['MATERIAL_ID'] == sdf.loc[index, 'Component Material']].index[0]
            if sdf.loc[index, 'UOM'] == mmdf.loc[mmindex, 'UOM_B']:
                sdf.loc[index, 'price'] = float("{0:.3f}".format(sdf.loc[index, 'Qty'] * mmdf.loc[mmindex, 'Price']))
            else:
                """print("apply uom conversion before calculating the price")"""
                altindex = altuomdf.loc[(altuomdf['Material_ID'] == sdf.loc[index, 'Component Material'])
                                        & (altuomdf['UoM'] == sdf.loc[index, 'UOM'])].index[0]
                sdf.loc[index, 'price'] = float("{0:.3f}".format(sdf.loc[index, 'Qty'] * altuomdf.loc[altindex, 'N'] \
                                                                 * mmdf.loc[mmindex, 'Price'] / altuomdf.loc[
                                                                     altindex, 'D']))
        else:
            """No price if UOM is not valid"""
            sdf.loc[index, 'price'] = np.nan
        """Generate new unique item_identifier for SAP"""
        if prevsapbomdf.empty:
            if curritemid < 9999 and sdf.loc[index, 'discardbom'] == False:
                sdf.loc[index, 'item_identifier'] = curritemid
                curritemid += 1
            else:
                print("Ran out of valid item identifier")
        else:
            prevbomindex = prevsapbomdf.loc[(prevsapbomdf['Header Material'] == sdf.loc[index, 'Header Material'])
                                    & (prevsapbomdf['Component Material'] == sdf.loc[index, 'Component Material'])]
            if len(prevbomindex) != 0:
                sdf.loc[index, 'item_identifier'] = prevsapbomdf.loc[prevbomindex.index[0], 'item_identifier']
            else:
                if curritemid < 9999 and sdf.loc[index, 'discardbom'] == False:
                    sdf.loc[index, 'item_identifier'] = curritemid
                    curritemid += 1
                else:
                    print("Ran out of valid item identifier")
    exportsapbom(sdf)


def addquantity(somedf, value1, value2):
    """Add the value of two similar bom records into one"""
    somedf.loc[value1, 'Qty'] += somedf.loc[value2, 'Qty']
    if somedf.loc[value1, 'Source'] != somedf.loc[value2, 'Source']:
        somedf.loc[value1, 'Source'] = "Both"
    somedf.loc[value2, 'discardbom'] = True
    return somedf


def checkmaterial(somedf, mmdf, currindex):
    """ check whether header are present in the material master"""
    headerfound = mmdf.loc[mmdf['MATERIAL_ID'] == somedf.loc[currindex, 'Header Material']]
    if len(headerfound) != 0:
        somedf.loc[currindex, 'valid_header'] = True
    else:
        somedf.loc[currindex, 'valid_header'] = False
    """ check whether component are present in the material master """
    componentfound = mmdf.loc[mmdf['MATERIAL_ID'] == somedf.loc[currindex, 'Component Material']]
    if len(componentfound) != 0:
        somedf.loc[currindex, 'valid_component'] = True
        """ validate component UOM """
        if (somedf.loc[currindex, 'UOM'] == mmdf.loc[componentfound.index[0], 'UOM_B']) \
                or (somedf.loc[currindex, 'UOM'] == mmdf.loc[componentfound.index[0], 'UOM_P']) \
                or (somedf.loc[currindex, 'UOM'] == mmdf.loc[componentfound.index[0], 'UOM_I']):
            somedf.loc[currindex, 'valid_c_uom'] = True
    else:
        somedf.loc[currindex, 'valid_component'] = False
        somedf.loc[currindex, 'valid_c_uom'] = False

    """return final dataframe with bom record updated"""
    return somedf


def cleanmaterialmaster(mmdf):
    mmdf.dropna(subset=["MATERIAL_ID"], inplace=True)
    return mmdf


def cleanaltuom(altuomdf):
    return altuomdf


def exportsapbom(sapbomdf):
    indexnames = sapbomdf[sapbomdf['discardbom'] == True].index
    sapbomdf.drop(indexnames, inplace=True)
    sapbomdf.to_csv("sapbomdf.csv")
    print("sapbomdf.csv has been created")


def main():
    generatebom()


if __name__ == '__main__':
    main()
