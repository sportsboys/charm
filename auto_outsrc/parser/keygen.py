import sdlpath
from sdlparser.SDLParser import *
from transformNEW import *
from secretListInKeygen import getSecretList
from outsrctechniques import SubstituteVar, GetAttributeVars
import sys

linesOfCode = None
assignInfo = None
varTypes = None
astNodes = None
forLoops = None
publicVarNames = None
secretVarNames = None
varDepList = None
blindingFactors_Lists = []
blindingFactors_NonLists = []
varsThatAreBlinded = []
varsNameToSecretVarsUsed = {}
sharedBlindingFactorNames = {}
sharedBlindingFactorCounter = 0
#namesOfAllNonListBlindingFactors = []
mappingOfSecretVarsToBlindingFactors = {}
mappingOfSecretVarsToGroupType = {}
keygenElemToExponents = {}
keygenElemToSMTExp = {}
SMTaddCounter = 0
SMTmulCounter = 0
#SMTleafCounter = 0
secretKeyElements = []
masterSecretKeyElements = []
allMskAndRndVars = []

mskVars = []
rndVars = []

def processListOrExpandNodes(binNode, origVarName, newVarName):
    binNodeRight = binNode.right
    if (binNodeRight == None):
        return

    binNodeRightType = binNodeRight.type
    if ( (binNodeRightType != ops.LIST) and (binNodeRightType != ops.EXPAND) ):
        return

    nodeListNodes = binNodeRight.listNodes
    if (len(nodeListNodes) == 0):
        return

    retNodeList = []

    for currentNode in nodeListNodes:
        if (currentNode == origVarName):
            retNodeList.append(newVarName)
        else:
            retNodeList.append(currentNode)

    binNodeRight.listNodes = retNodeList

def replaceVarInstancesInLineNoRange(startLineNo, endLineNo, origVarName, newVarName):
    for lineNoIndex in range(startLineNo, (endLineNo + 1)):
        indexIntoCodeStructs = lineNoIndex - 1
        currentBinNode = astNodes[indexIntoCodeStructs]
        ASTVisitor(SubstituteVar(origVarName,newVarName)).preorder(currentBinNode)
        processListOrExpandNodes(currentBinNode, origVarName, newVarName)
        binNodeAsString = str(currentBinNode)
        if (binNodeAsString == 'NONE'):
            binNodeAsString = "\n"
        substituteOneLineOfCode(binNodeAsString, lineNoIndex)

    updateCodeAndStructs()

def updateCodeAndStructs():
    global linesOfCode, assignInfo, varTypes, astNodes, forLoops, publicVarNames, secretVarNames, varDepList

    parseLinesOfCode(getLinesOfCode(), False)
    linesOfCode = getLinesOfCode()
    assignInfo = getAssignInfo()
    varTypes = getVarTypes()
    astNodes = getAstNodes()
    forLoops = getForLoops()
    publicVarNames = getPublicVarNames()
    secretVarNames = getSecretVarNames()
    varDepList = externalGetVarDepList()

def writeLinesToFuncAfterVarLastAssign(funcName, lineList, varName):
    if (varName == None):
        lineNo = getLineNoOfInputStatement(funcName) + 1
    else:
        lineNo = getLineNoOfLastAssign(funcName, varName) + 1
        if (lineNo == 1):
            lineNo = getLineNoOfInputStatement(funcName) + 1

    appendToLinesOfCode(lineList, lineNo)
    updateCodeAndStructs()
    return (lineNo + (len(lineList)))

def getLineNosOfAllAssigns(funcName, varNameToFind):
    if (funcName not in assignInfo):
        sys.exit("getLineNosOfAllAssigns in keygen.py:  funcName is not in assignInfo.")

    lineNos = []

    for currentVarName in assignInfo[funcName]:
        currentVarName_NoIndices = removeListIndices(currentVarName)
        if (currentVarName_NoIndices != varNameToFind):
            continue

        currentLineNo = assignInfo[funcName][currentVarName].getLineNo()
        lineNos.append(currentLineNo)

    return lineNos

def getLineNoOfLastAssign(funcName, varNameToFind):
    if (funcName not in assignInfo):
        sys.exit("getLineNoOfLastAssign in keygen.py:  funcName is not in assignInfo.")

    lastLineNo = 0

    for currentVarName in assignInfo[funcName]:
        currentVarName_NoIndices = removeListIndices(currentVarName)
        if (currentVarName_NoIndices != varNameToFind):
            continue

        currentLineNo = assignInfo[funcName][currentVarName].getLineNo()

        if (currentLineNo > lastLineNo):
            lastLineNo = currentLineNo

    #if (lastLineNo == 0):
        #sys.exit("getLineNoOfLastAssign in keygen.py:  could not find any line numbers matching the variable name and function name passed in.")

    possibleNewLastLineNo = getEndLineNoOfForLoop(funcName, lastLineNo)
    if (possibleNewLastLineNo != 0):
        lastLineNo = possibleNewLastLineNo + 1

    return lastLineNo

def getIsVarList(keygenOutputElem, keygenOutputVarInfo):
    if ( (keygenOutputVarInfo.getIsList() == True) or (keygenOutputVarInfo.getIsSymmap() == True) or (len(keygenOutputVarInfo.getListNodesList()) > 0) ):
        return True

    if (str(keygenOutputVarInfo.getAssignNode().left).find(LIST_INDEX_SYMBOL) != -1):
        return True

    try:
        currentVarType = varTypes[TYPES_HEADER][keygenOutputElem].getType()
    except:
        return False

    if (currentVarType == ops.LIST):
        sys.exit("getIsVarList in keygen.py:  currentVarType is ops.LIST, not types.list.")

    if (currentVarType == types.list):
        return True

    return False

def removeListIndices(inputString):
    inputStringSplit = inputString.split(LIST_INDEX_SYMBOL)
    return inputStringSplit[0]

def removeListIndicesAndDupsFromList(inputList):
    retList = []

    for inputListEntry in inputList:
        entryWithoutIndices = removeListIndices(inputListEntry)
        if (entryWithoutIndices not in retList):
            retList.append(entryWithoutIndices)

    return retList

def writeForAllLoop(keygenOutputElem, varsToBlindList, varNamesForListDecls, sharedBlindingFactorName, repeatBlindingFactor):
    global blindingFactors_Lists, varsThatAreBlinded, blindingFactors_NonLists
    global mappingOfSecretVarsToBlindingFactors

    sameMasterSecret = False

    listBlindingFactorName = blindingFactorPrefix + keygenOutputElem + blindingSuffix
    #(sharedBlindingFactorName, repeatBlindingFactor) = getCurrentBlindingFactorName(keygenOutputElem)
    if (listBlindingFactorName != sharedBlindingFactorName):
        sameMasterSecret = True

    if (sameMasterSecret == False):
        blindingFactors_Lists.append(listBlindingFactorName)

    varsThatAreBlinded.append(keygenOutputElem)

    SDLLinesForKeygen = []

    #SDLLinesForKeygen.append(blindingLoopVarLength + " := len(" + keygenOutputElem + ")\n")

    #SDLLinesForKeygen.append(keygenOutputElem + keysForKeygenElemSuffix + " := " + KEYS_FUNC_NAME + "(" + keygenOutputElem + ")\n")

    SDLLinesForKeygen.append("BEGIN :: forall\n")
    #SDLLinesForKeygen.append("BEGIN :: for\n")

    SDLLinesForKeygen.append("forall{" + blindingLoopVar + " := " + keygenOutputElem + "}\n")
    #SDLLinesForKeygen.append("for{" + blindingLoopVar + " := 0, " + blindingLoopVarLength + "}\n")

    #SDLLinesForKeygen.append(keygenOutputElem + loopVarForKeygenElemKeys + " := " + keygenOutputElem + keysForKeygenElemSuffix + LIST_INDEX_SYMBOL + blindingLoopVar + "\n")

    if (sameMasterSecret == True):
        SDLLinesForKeygen.append(listBlindingFactorName + LIST_INDEX_SYMBOL + blindingLoopVar + " := " + sharedBlindingFactorName + "\n")
        if (sharedBlindingFactorName not in blindingFactors_NonLists):
            blindingFactors_NonLists.append(sharedBlindingFactorName)
    else:
        SDLLinesForKeygen.append(listBlindingFactorName + LIST_INDEX_SYMBOL + blindingLoopVar + " := random(ZR)\n")

    SDLLinesForKeygen.append(keygenOutputElem + blindingSuffix + LIST_INDEX_SYMBOL + blindingLoopVar + " := " + keygenOutputElem + LIST_INDEX_SYMBOL + blindingLoopVar + " ^ (1/" + listBlindingFactorName + LIST_INDEX_SYMBOL + blindingLoopVar + ")\n")

    SDLLinesForKeygen.append("END :: forall\n")
    #SDLLinesForKeygen.append("END :: for\n")

    if (sameMasterSecret == True):
        mappingOfSecretVarsToBlindingFactors[keygenOutputElem] = [sharedBlindingFactorName]
    else:
        mappingOfSecretVarsToBlindingFactors[keygenOutputElem] = [listBlindingFactorName]
        mappingOfSecretVarsToBlindingFactors[keygenOutputElem].append(listNameIndicator)

    #varsToBlindList.remove(keygenOutputElem)
    if (keygenOutputElem in varNamesForListDecls):
        sys.exit("writeForAllLoop in keygen.py attempted to add duplicate keygenOutputElem to varNamesForListDecls -- 2 of 2.")

    #if (sameMasterSecret == False):
    varNamesForListDecls.append(keygenOutputElem)

    lineNoAfterThisAddition = writeLinesToFuncAfterVarLastAssign(keygenFuncName, SDLLinesForKeygen, keygenOutputElem)
    replaceVarInstancesInLineNoRange(lineNoAfterThisAddition, getEndLineNoOfFunc(keygenFuncName), keygenOutputElem, (keygenOutputElem + blindingSuffix))

def varListContainsParentDict(varList, parentDict):
    for varName in varList:
        varNameWithoutIndices = removeListIndices(varName)
        if (varNameWithoutIndices == parentDict):
            return True

    return False

def getShouldThisElemBeUnblinded(keygenOutputElem, varsModifiedInKeygen, keygenFuncName):
    if (keygenOutputElem == keygenSecVar):
        return False

    if (keygenOutputElem in publicVarNames):
        return True

    if ( (keygenOutputElem not in secretVarNames) and (keygenOutputElem not in varsModifiedInKeygen) ):
        return True

    if (keygenFuncName not in varDepList):
        sys.exit("getShouldThisElemBeUnblinded in keygen.py:  keygen function name is not in varDepList.")

    if (keygenOutputElem not in varDepList[keygenFuncName]):
        sys.exit("getShouldThisElemBeUnblinded in keygen.py:  keygenOutputElem parameter passed in is not in varDepList[keygenFuncName].")

    varDepsOfThisElem = varDepList[keygenFuncName][keygenOutputElem]

    for varDep in varDepsOfThisElem:
        tempVarDep = varDep
        listSymIndex = tempVarDep.find(LIST_INDEX_SYMBOL)
        if (listSymIndex != -1):
            tempVarDep = tempVarDep[0:listSymIndex]
        if (tempVarDep in secretVarNames):
            return False

    return True

def getSecretVarsUsed(keygenOutputElem, keygenFuncName):
    retList = []

    if keygenOutputElem not in varDepList[keygenFuncName]:
        return []

    varDepsOfThisElem = varDepList[keygenFuncName][keygenOutputElem]

    for varDep in varDepsOfThisElem:
        tempVarDep = varDep
        listSymIndex = tempVarDep.find(LIST_INDEX_SYMBOL)
        if (listSymIndex != -1):
            #tempVarDep = tempVarDep[0:listSymIndex]
            pass
        #if (tempVarDep in secretVarNames):
        if (isVarNameInList(tempVarDep, secretVarNames) == True):
            if (tempVarDep not in retList):
                retList.append(tempVarDep)

    return retList

def isVarNameInList(varName, varList):
    listSymIndex = varName.find(LIST_INDEX_SYMBOL)
    if (listSymIndex != -1):
        varName = varName[0:listSymIndex]

    if (varName in varList):
        return True

    return False

def getElementsOfSameGroupType(keygenOutputElem):
    retList = []

    groupTypeOfThisElement = mappingOfSecretVarsToGroupType[keygenOutputElem]

    for currentElement in mappingOfSecretVarsToGroupType:
        currentGroupType = mappingOfSecretVarsToGroupType[currentElement]
        if ( (currentGroupType == groupTypeOfThisElement) and (currentElement != keygenOutputElem) ):
            retList.append(currentElement)

    return retList

def getBlindingNonListFactorsOfSameGroupType(elementsOfSameGroupType):
    retList = []

    for element in elementsOfSameGroupType:
        if element not in mappingOfSecretVarsToBlindingFactors:
            continue
        currentBlindingFactorList = mappingOfSecretVarsToBlindingFactors[element]
        if ( (currentBlindingFactorList[0] not in retList) and (currentBlindingFactorList[0] in blindingFactors_NonLists) ):
            retList.append(currentBlindingFactorList[0])

    return retList

def getCurrentBlindingFactorName(keygenOutputElem):
    global sharedBlindingFactorNames, sharedBlindingFactorCounter, blindingFactors_NonLists
    #global namesOfAllNonListBlindingFactors

    groupTypeOfThisElement = mappingOfSecretVarsToGroupType[keygenOutputElem]

    elementsOfSameGroupType = getElementsOfSameGroupType(keygenOutputElem)

    #print("current element is ", keygenOutputElem)
    #print("of same type are ", elementsOfSameGroupType)

    blindingNonListFactorsOfSameGroupType = getBlindingNonListFactorsOfSameGroupType(elementsOfSameGroupType)

    #print("BFs of same group type:  ", blindingNonListFactorsOfSameGroupType)

    if (len(blindingNonListFactorsOfSameGroupType) > 1):
        sys.exit("getCurrentBlindingFactorName in keygen.py:  more than one blinding factor of same group type; should never happen -- error in system logic.")

    if (len(blindingNonListFactorsOfSameGroupType) == 1):
        return (blindingNonListFactorsOfSameGroupType[0], True)

    if (len(varsNameToSecretVarsUsed[keygenOutputElem]) > 1):
        return (blindingFactorPrefix + keygenOutputElem + blindingSuffix, False)

    secretVarForThisKeygenElem = varsNameToSecretVarsUsed[keygenOutputElem][0]

    if (secretVarForThisKeygenElem in sharedBlindingFactorNames):
        return (sharedBlindingFactorNames[secretVarForThisKeygenElem], True)

    sharedBlindingFactorNames[secretVarForThisKeygenElem] = blindingFactorPrefix + str(sharedBlindingFactorCounter) + blindingSuffix
    sharedBlindingFactorCounter += 1

    if (sharedBlindingFactorNames[secretVarForThisKeygenElem] not in blindingFactors_NonLists):
        blindingFactors_NonLists.append(sharedBlindingFactorNames[secretVarForThisKeygenElem])

    #if (sharedBlindingFactorNames[secretVarForThisKeygenElem] not in namesOfAllNonListBlindingFactors):
        #namesOfAllNonListBlindingFactors.append(sharedBlindingFactorNames[secretVarForThisKeygenElem])

    return (sharedBlindingFactorNames[secretVarForThisKeygenElem], False)

def rearrangeListWRTSecretVars(inputList, keygenFuncName):
    mappingOfVarNameToSecretVarsUsedLocal = {}

    for element in inputList:
        secretVarsUsed = getSecretVarsUsed(element, keygenFuncName)
        mappingOfVarNameToSecretVarsUsedLocal[element] = secretVarsUsed

    outputList = []

    for element in mappingOfVarNameToSecretVarsUsedLocal:
        if (len(mappingOfVarNameToSecretVarsUsedLocal[element]) > 0):
            outputList.append(element)

    for element in mappingOfVarNameToSecretVarsUsedLocal:
        if (element not in outputList):
            outputList.append(element)

    return outputList

def getVarsUsedInFuncs(funcName):
    retList = []

    if funcName not in assignInfo:
        sys.exit("getVarsUsedInFuncs in keygen.py:  function name passed in is not in AssignInfo.")

    varsInThatFunc = assignInfo[funcName]

    for currentVarName in varsInThatFunc:
        varInfoObj = varsInThatFunc[currentVarName]
        assignNode = varInfoObj.getAssignNode()
        assignNodeRight = assignNode.right
        if (assignNodeRight.type != ops.FUNC):
            continue

        if (str(assignNodeRight.attr) == LEN_FUNC_NAME):
            continue

        for listNode in assignNodeRight.listNodes:
            if (listNode not in retList):
                retList.append(listNode)

    return retList

def useAlternateBlinding(keygenOutputElem):
    return False

    elementType = getVarTypeInfoRecursive(BinaryNode(keygenOutputElem), keygenFuncName)

    decryptVarsUsedInFuncs = getVarsUsedInFuncs(decryptFuncName)
    if (keygenOutputElem in decryptVarsUsedInFuncs):
        return False

    if (elementType in [types.G1, types.G2, types.GT, types.ZR]):
        return True

    if (elementType in [types.listG1, types.listG2, types.listGT, types.listZR]):
        return True

    return False

def getWhichNonListBFToShare():
    if (len(sharedBlindingFactorNames) == 0):
        return blindingFactors_NonLists[0]

    for keyName in sharedBlindingFactorNames:
        return sharedBlindingFactorNames[keyName]

def addExponentsToAllMskAndRndVarsList(node):
    global allMskAndRndVars

    allExponentNames = GetAttributeVars(node, True)

    for exp in allExponentNames:
        if (exp not in allMskAndRndVars):
            allMskAndRndVars.append(exp)

def searchForExponentsRecursive(node, exponentsList, levelNumber):
    if (node.type == ops.EXP):
        if (str(node.right) not in exponentsList):
            exponentsList.append((node.right, levelNumber + 1))
            addExponentsToAllMskAndRndVarsList(node.right)
    #else:
    if (node.left != None):
        if (node.type == ops.EXP):
            searchForExponentsRecursive(node.left, exponentsList, levelNumber - 1)
        else:
            searchForExponentsRecursive(node.left, exponentsList, levelNumber)
    if (node.right != None):
        if (node.type == ops.EXP):
            searchForExponentsRecursive(node.right, exponentsList, levelNumber + 1)
        else:
            searchForExponentsRecursive(node.right, exponentsList, levelNumber)

def arrangeExponentsForArithmetic(exponentsList):
    expression = ""
    previousLevelNumber = -9999

    if (len(exponentsList) == 0):
        return []

    if (len(exponentsList) == 1):
        return [exponentsList[0][0]]

    exponent = exponentsList[0][0]
    previousLevelNumber = exponentsList[0][1]

    expression += str(exponent)

    firstOne = True

    for indivEntry in exponentsList:
        if (firstOne == True):
            firstOne = False
            continue

        exponent = indivEntry[0]
        currentLevelNumber = indivEntry[1]

        if (previousLevelNumber <= currentLevelNumber):
            expression += " + "
        else:
            expression += " * "

        expression += str(exponent)

        previousLevelNumber = currentLevelNumber

    parser = SDLParser()
    node = parser.parse(expression)

    return [node]

def searchForExponents(node):
    exponentsList = []

    searchForExponentsRecursive(node, exponentsList, 0)
    exponentsArrangedForArithmetic = arrangeExponentsForArithmetic(exponentsList)
    return exponentsArrangedForArithmetic

def shouldWeUseFullBaseElems(keygenOutputElem, config):
    if (keygenOutputElem not in assignInfo[config.keygenFuncName]):
        sys.exit("shouldWeUseFullBaseElems in keygen.py:  keygenOutputElem parameter passed in is not in assignInfo[keygenFuncName].")

    assignInfoVarEntry = assignInfo[config.keygenFuncName][keygenOutputElem]
    baseElemsOnlyNode = assignInfoVarEntry.getAssignBaseElemsOnlyThisFunc()
    baseElemsOnly = GetAttributeVars(baseElemsOnlyNode, True)
    for baseElem in baseElemsOnly:
        if baseElem in masterSecretKeyElements:
            groupTypeOfThisElem = getVarTypeInfoRecursive(BinaryNode(baseElem), config.setupFuncName)
            if (groupTypeOfThisElem in [types.G1, types.G2, types.GT]):
                return True

    return False

def getKeygenElemToExponentsDictEntry(keygenOutputElem, keygenFuncName, config):
    global keygenElemToExponents

    if (keygenOutputElem not in assignInfo[keygenFuncName]):
        #sys.exit("getKeygenElemToExponentsDictEntry in keygen.py:  keygenOutputElem parameter passed in is not in assignInfo[keygenFuncName].")
        keygenElemToExponents[keygenOutputElem] = []
        return

    assignInfoVarEntry = assignInfo[keygenFuncName][keygenOutputElem]
    useFullBaseElems = shouldWeUseFullBaseElems(keygenOutputElem, config)
    if (useFullBaseElems == True):
        baseElemsOnly = assignInfoVarEntry.getAssignBaseElemsOnly()
    else:
        baseElemsOnly = assignInfoVarEntry.getAssignBaseElemsOnlyThisFunc()

    if (baseElemsOnly.type != ops.LIST):
        baseElemsOnly = makeReplacementsForMasterPublicVars(baseElemsOnly, config)

    keygenElemToExponents[keygenOutputElem] = searchForExponents(baseElemsOnly)

    #print(baseElemsOnly)

def getAllMasterPubVarsAsStrings(config):
    if (config.setupFuncName not in assignInfo):
        sys.exit("getAllMasterPubVarsAsStrings in keygen.py:  config.setupFuncName not in assignInfo.")

    retList = {}

    for mpk in config.masterPubVars:
        if (mpk not in assignInfo[config.setupFuncName]):
            sys.exit("getAllMasterPubVarsAsStrings in keygen.py:  one of the pub vars was not in assignInfo[config.setupFuncName].")

        mpkVarInfoObj = assignInfo[config.setupFuncName][mpk]
        mpkVarDeps = mpkVarInfoObj.getVarDeps()
        for mpkVarDep in mpkVarDeps:
            if (mpkVarDep not in assignInfo[config.setupFuncName]):
                continue #I wanted to throw an error here, but LW would be a problem if I did, so continue is fine for now

            if (mpkVarDep in retList):
                continue

            baseElemsOnly = assignInfo[config.setupFuncName][mpkVarDep].getAssignBaseElemsOnly()
            retList[mpkVarDep] = str(baseElemsOnly)

    return retList

def ensureParenthesesAround(inputString):
    if (inputString[0] != "("):
        inputString = "(" + inputString

    lenInputString = len(inputString)

    if (inputString[(lenInputString - 1)] != ")"):
        inputString = inputString + ")"

    return inputString

def makeReplacementsForMasterPublicVars(node, config):
    nodeAsStr = str(node)
    masterPubVarsAsStrings = getAllMasterPubVarsAsStrings(config)
    for mpkString in masterPubVarsAsStrings:
        whatToReplaceWith = mpkString
        whatToLookFor = (masterPubVarsAsStrings[mpkString])
        #putting parenthese around everything means we might not catch something, but so be it
        whatToLookFor = ensureParenthesesAround(whatToLookFor)
        #print("what to look for:  ", whatToLookFor)
        #print("what to replace with:  ", whatToReplaceWith)
        if (whatToLookFor == whatToReplaceWith):
            continue

        nodeAsStr = nodeAsStr.replace(whatToLookFor, whatToReplaceWith)

    #print(node)
    #print(nodeAsStr)

    parser = SDLParser()
    newNode = parser.parse(nodeAsStr)
    return newNode

def getAllKeygenElemsToExponentsDictEntries(keygenOutputElem, keygenFuncName, config):
    #global keygenElemToExponents
    global secretKeyElements

    if (keygenOutputElem not in secretKeyElements):
        secretKeyElements.append(keygenOutputElem)

    getKeygenElemToExponentsDictEntry(keygenOutputElem, keygenFuncName, config)

    if (keygenOutputElem not in assignInfo[keygenFuncName]):
        return

    keygenOutputVarInfo = assignInfo[keygenFuncName][keygenOutputElem]

    if ( (keygenOutputVarInfo.getIsList() == True) and (len(keygenOutputVarInfo.getListNodesList()) > 0) ):
        listMembers = keygenOutputVarInfo.getListNodesList()
        listMembersORIGINAL = listMembers
        listMembers = rearrangeListWRTSecretVars(listMembers, keygenFuncName)

        for listMember in listMembers:
            getAllKeygenElemsToExponentsDictEntries(listMember, keygenFuncName, config)

def getIndividualKeygenElemToSMTExpression(exponents, rootNodeName, leafNodeName, config):
    global SMTaddCounter, SMTmulCounter

    SMTaddCounter = 0
    SMTmulCounter = 0
    #SMTleafCounter = 0

    retExpression = {}

    if (len(exponents) == 0):
        return {}

    retExpression[rootNodeName] = []

    if ( (len(exponents) == 1) and (exponents[0].type == ops.ATTR) ):
        retExpression[rootNodeName].append(leafNodeName)
        retExpression[leafNodeName] = []
        retExpression[leafNodeName].append(str(exponents[0]))
        return retExpression

    if (len(exponents) == 1):
        getSMTExpressionForOneExponent(exponents[0], rootNodeName, retExpression, config)
        return retExpression

    currentKey = config.addNodePrefix+str(SMTaddCounter)
    SMTaddCounter += 1
    retExpression[rootNodeName].append(currentKey)
    retExpression[currentKey] = []

    for exponent in exponents:
        getSMTExpressionForOneExponent(exponent, currentKey, retExpression, config)

    return retExpression

def getSMTExpressionForOneExponent(exponent, parentKey, retExpression, config):
    global SMTaddCounter, SMTmulCounter

    if ( (exponent.type == ops.ADD) or (exponent.type == ops.SUB) ):
        currentKey = config.addNodePrefix+str(SMTaddCounter)
        SMTaddCounter += 1
        if (parentKey != None):
            retExpression[parentKey].append(currentKey)
        retExpression[currentKey] = []
        getSMTExpressionForOneExponent(exponent.left, currentKey, retExpression, config)
        getSMTExpressionForOneExponent(exponent.right, currentKey, retExpression, config)

    if ( (exponent.type == ops.MUL) or (exponent.type == ops.DIV) ):
        currentKey = config.mulNodePrefix+str(SMTmulCounter)
        SMTmulCounter += 1
        if (parentKey != None):
            retExpression[parentKey].append(currentKey)
        retExpression[currentKey] = []
        getSMTExpressionForOneExponent(exponent.left, currentKey, retExpression, config)
        getSMTExpressionForOneExponent(exponent.right, currentKey, retExpression, config)

    if (exponent.type == ops.ATTR):
        retExpression[parentKey].append(str(exponent))

'''
def getSMTExpressionForOneExponent(exponent):
    pass

def getIndividualKeygenElemToSMTExpression(exponents):
    retExpression = {}

    #print(exponents)

    if (len(exponents) == 0):
        return {}

    if (len(exponents) == 1):
        if (exponents[0].type == ops.ATTR):
            retExpression['root'] = str(exponents[0])
        else:
            retExpression['root'] = getSMTExpressionForOneExponent(exponents[0])

        return retExpression

    retExpression['root'] = 'ADD0'
    retExpression['ADD0'] = []

    for exponent in exponents:
        if (exponent.type == ops.ATTR):
            retExpression['ADD0'].append(str(exponent))
            continue

        nextExpToAdd = getSMTExpressionForOneExponent(exponent)
        retExpression['ADD0'].append(nextExpToAdd)

    return retExpression
'''

def addMskRndVars(config):
    global keygenElemToSMTExp, mskVars, rndVars

    #keygenElemToSMTExp[mskVars] = []
    #keygenElemToSMTExp[rndVars] = []

    for exp in allMskAndRndVars:
        if ( (exp in assignInfo[config.setupFuncName]) and (exp not in assignInfo[config.keygenFuncName]) ):
            if (exp not in mskVars):
                mskVars.append(exp)
        elif ( (exp not in assignInfo[config.setupFuncName]) and (exp in assignInfo[config.keygenFuncName]) ):
            if (exp not in rndVars):
                rndVars.append(exp)
        else:
            sys.exit("addMskRndVars in keygen.py:  exponent name is supposed to appear in either config.setupFuncName or config.keygenFuncName, but not both and not neither, which is what is happening here.")

def getKeygenElemToSMTExpressions(rootNodeName, leafNodeName, config):
    global keygenElemToSMTExp

    for keygenElemToExp in keygenElemToExponents:
        #print(keygenElemToExp)
        #print(keygenElemToExponents[keygenElemToExp])
        #print("\n\n")

        if (keygenElemToExp == config.keygenSecVar):
            secVarRetList = []
            for secretKeyElem in secretKeyElements:
                if (secretKeyElem != config.keygenSecVar):
                    secVarRetList.append(secretKeyElem)
            keygenElemToSMTExp[keygenElemToExp] = secVarRetList
        else:
            exponents = keygenElemToExponents[keygenElemToExp]
            keygenElemToSMTExp[keygenElemToExp] = getIndividualKeygenElemToSMTExpression(exponents, rootNodeName, leafNodeName, config)

    addMskRndVars(config)

def blindKeygenOutputElement(keygenOutputElem, varsToBlindList, varNamesForListDecls, keygenFuncName):
    global blindingFactors_NonLists, varsThatAreBlinded, varsNameToSecretVarsUsed
    global mappingOfSecretVarsToBlindingFactors, mappingOfSecretVarsToGroupType
    #global keygenElemToExponents
    global secretKeyElements

    #keygenElemToExponents[keygenOutputElem] = []
    #getKeygenElemToExponentsDictEntry(keygenOutputElem)

    #print(keygenElemToExponents)

    if (keygenOutputElem not in secretKeyElements):
        secretKeyElements.append(keygenOutputElem)

    groupTypeOfThisElement = getVarTypeInfoRecursive(BinaryNode(keygenOutputElem), keygenFuncName)
    mappingOfSecretVarsToGroupType[keygenOutputElem] = groupTypeOfThisElement

    SDLLinesForKeygen = []

    varsModifiedInKeygen = list(assignInfo[keygenFuncName].keys())
    varsModifiedInKeygen = removeListIndicesAndDupsFromList(varsModifiedInKeygen)

    shouldThisElemBeUnblinded = getShouldThisElemBeUnblinded(keygenOutputElem, varsModifiedInKeygen, keygenFuncName)

    if (shouldThisElemBeUnblinded == True):
        #if (isGroupElement(keygenOutputElem) == False):
        if ( (useAlternateBlinding(keygenOutputElem) == False) or (len(blindingFactors_NonLists) == 0) or (keygenOutputElem not in assignInfo[keygenFuncName]) ):
            varsNameToSecretVarsUsed[keygenOutputElem] = []
            SDLLinesForKeygen.append(keygenOutputElem + blindingSuffix + " := " + keygenOutputElem + "\n")
            lineNoAfterThisAddition = writeLinesToFuncAfterVarLastAssign(keygenFuncName, SDLLinesForKeygen, keygenOutputElem)
            replaceVarInstancesInLineNoRange(lineNoAfterThisAddition, getEndLineNoOfFunc(keygenFuncName), keygenOutputElem, (keygenOutputElem + blindingSuffix))
            return keygenOutputElem
        varsNameToSecretVarsUsed[keygenOutputElem] = []
        currentBlindingFactorName = getWhichNonListBFToShare()
        repeatBlindingFactor = True
    else:
        secretVarsUsed = getSecretVarsUsed(keygenOutputElem, keygenFuncName)
        varsNameToSecretVarsUsed[keygenOutputElem] = secretVarsUsed
        (currentBlindingFactorName, repeatBlindingFactor) = getCurrentBlindingFactorName(keygenOutputElem)

    if (keygenOutputElem not in assignInfo[keygenFuncName]):
        if (varListContainsParentDict(assignInfo[keygenFuncName].keys(), keygenOutputElem) == False):
            sys.exit("keygen output element passed to blindKeygenOutputElement in keygen.py is not in assignInfo[keygenFuncName], and is not a parent dictionary of one of the variables in assignInfo[keygenFuncName].")
        writeForAllLoop(keygenOutputElem, varsToBlindList, varNamesForListDecls, currentBlindingFactorName, repeatBlindingFactor)
        return keygenOutputElem

    keygenOutputVarInfo = assignInfo[keygenFuncName][keygenOutputElem]

    isVarList = getIsVarList(keygenOutputElem, keygenOutputVarInfo)

    #currentBlindingFactorName = blindingFactorPrefix + keygenOutputElem + blindingSuffix

    if (isVarList == False):
        if (repeatBlindingFactor == False):
            if (currentBlindingFactorName not in blindingFactors_NonLists):
                blindingFactors_NonLists.append(currentBlindingFactorName)
            #SDLLinesForKeygen.append(currentBlindingFactorName + " := random(ZR)\n")
            #blindingFactors_NonLists.append(currentBlindingFactorName)
        varsThatAreBlinded.append(keygenOutputElem)
        SDLLinesForKeygen.append(keygenOutputElem + blindingSuffix + " := " + keygenOutputElem + " ^ (1/" + currentBlindingFactorName + ")\n")
        mappingOfSecretVarsToBlindingFactors[keygenOutputElem] = [currentBlindingFactorName]
        #varsToBlindList.remove(keygenOutputElem)
        lineNoAfterThisAddition = writeLinesToFuncAfterVarLastAssign(keygenFuncName, SDLLinesForKeygen, keygenOutputElem)
        replaceVarInstancesInLineNoRange(lineNoAfterThisAddition, getEndLineNoOfFunc(keygenFuncName), keygenOutputElem, (keygenOutputElem + blindingSuffix))
        return keygenOutputElem

    if ( (keygenOutputVarInfo.getIsList() == True) and (len(keygenOutputVarInfo.getListNodesList()) > 0) ):
        listMembers = keygenOutputVarInfo.getListNodesList()
        listMembersORIGINAL = listMembers
        listMembers = rearrangeListWRTSecretVars(listMembers, keygenFuncName)
        listMembersString = ""
        for listMember in listMembers:
            #listMembersString += listMember + blindingSuffix + ", "
            blindKeygenOutputElement(listMember, varsToBlindList, varNamesForListDecls, keygenFuncName)
        #listMembersString = listMembersString[0:(len(listMembersString)-2)]
        for listMember in listMembersORIGINAL:
            listMembersString += listMember + blindingSuffix + ", "
        listMembersString = listMembersString[0:(len(listMembersString) - 2)]
        SDLLinesForKeygen.append(keygenOutputElem + blindingSuffix + " := list{" + listMembersString + "}\n")
        if (keygenOutputElem in varNamesForListDecls):
            sys.exit("blindKeygenOutputElement in keygen.py attempted to add duplicate keygenOutputElem to varNamesForListDecls -- 1 of 2.")
        lineNoAfterThisAddition = writeLinesToFuncAfterVarLastAssign(keygenFuncName, SDLLinesForKeygen, keygenOutputElem)
        replaceVarInstancesInLineNoRange(lineNoAfterThisAddition, getEndLineNoOfFunc(keygenFuncName), keygenOutputElem, (keygenOutputElem + blindingSuffix))
        return keygenOutputElem

    writeForAllLoop(keygenOutputElem, varsToBlindList, varNamesForListDecls, currentBlindingFactorName, repeatBlindingFactor)
    return keygenOutputElem

def removeAssignmentOfOrigKeygenSecretKeyName(secretKeyName, keygenFuncName):
    assignLineNos = getLineNosOfAllAssigns(keygenFuncName, secretKeyName)    
    if (len(assignLineNos) == 0):
        sys.exit("removeAssignmentOfOrigKeygenSecretKeyName in keygen.py:  could not locate any assignment statements for the secret key name passed in (" + secretKeyName + ").")

    removeFromLinesOfCode(assignLineNos)

def getBlindingFactorsLine():
    outputLine = ""

    for blindingFactor_NonList in blindingFactors_NonLists:
        outputLine += blindingFactor_NonList + ", "

    for blindingFactor_List in blindingFactors_Lists:
        outputLine += blindingFactor_List + ", "

    outputLine = outputLine[0:(len(outputLine) - len(", "))]

    return outputLine

def writeOutputLineForKeygen(secretKeyName, keygenFuncName):
    SDLLinesForKeygen = []

    outputLine = ""

    outputLine += "output := list{"

    keygenOutput = assignInfo[keygenFuncName][outputKeyword].getVarDeps()
    for outputEntry in keygenOutput:
        if ( (outputEntry == keygenSecVar) or (outputEntry == (keygenSecVar + blindingSuffix)) ):
            continue

        outputLine += outputEntry + ", "

    outputLine += getBlindingFactorsLine() + ", "

    outputLine += secretKeyName + blindingSuffix + "}\n"

    SDLLinesForKeygen.append(outputLine)

    lineNoKeygenOutput = getLineNoOfOutputStatement(keygenFuncName)
    removeFromLinesOfCode([lineNoKeygenOutput])
    appendToLinesOfCode(SDLLinesForKeygen, lineNoKeygenOutput)
    updateCodeAndStructs()

def getMasterSecretKeyElements(config):
    global masterSecretKeyElements

    mskFunc = config.setupFuncName
    if (mskFunc not in assignInfo):
        sys.exit("getMasterSecretKeyElements in keygen.py:  setupFuncName from config file isn't in assignInfo.")

    mskFuncAssignInfoEntry = assignInfo[mskFunc]

    for mskElem in config.masterSecVars:
        if (mskElem not in mskFuncAssignInfoEntry):
            sys.exit("getMasterSecretKeyElements in keygen.py:  one of the var names in masterSecVars (from config file) isn't in assignInfo[name_of_setup_function_from_config_file].")

        assignInfoVarEntry = mskFuncAssignInfoEntry[mskElem]
        varDeps = assignInfoVarEntry.getVarDeps()
        for varDep in varDeps:
            if (varDep not in masterSecretKeyElements):
                masterSecretKeyElements.append(varDep)

    #print(masterSecretKeyElements)
    #sys.exit("test")

def keygen(file, config):
    #print(config.keygenFuncName)
 
    SDLLinesForKeygen = []

    if ( (type(file) is not str) or (len(file) == 0) ):
        sys.exit("First argument passed to keygen.py is invalid.")
        
#    config = importlib.import_module(configName) # __import__('config')
#    print("config: ", dir(config))
#    print("masterKeys: ", config.masterPubVars)
#    print("publicKeys: ", config.masterSecVars)
    
    parseFile2(file, False)

    varsToBlindList = getSecretList(config, False)

    varNamesForListDecls = []

    updateCodeAndStructs()

    getMasterSecretKeyElements(config)

    keygenFuncName = config.keygenFuncName

    if (keygenBlindingExponent in assignInfo[keygenFuncName]):
        sys.exit("keygen.py:  the variable used for keygenBlindingExponent in config.py already exists in the keygen function of the scheme being analyzed.")

    if ( (keygenFuncName not in assignInfo) or (outputKeyword not in assignInfo[keygenFuncName]) ):
        sys.exit("assignInfo structure obtained in keygen function of keygen.py did not have the right keygen function name or output keywords.")

    keygenOutput = assignInfo[keygenFuncName][outputKeyword].getVarDeps()
    if (len(keygenOutput) == 0):
        sys.exit("Variable dependencies obtained for output of keygen in keygen.py was of length zero.")

    SDLLinesForKeygen.append(keygenBlindingExponent + " := random(ZR)\n")
    lineNoAfterThisAddition = writeLinesToFuncAfterVarLastAssign(keygenFuncName, SDLLinesForKeygen, None)

    for keygenOutput_ind in keygenOutput:
        getAllKeygenElemsToExponentsDictEntries(keygenOutput_ind, keygenFuncName, config)

    #print(keygenElemToExponents)

    getKeygenElemToSMTExpressions(config.rootNodeName, config.leafNodeName, config)

    #print(keygenElemToSMTExp)
    #print("mskVars = ", mskVars)
    #print("rndVars = ", rndVars)
    #for elem in keygenElemToSMTExp:
        #print(elem, " = ", keygenElemToSMTExp[elem])
    #sys.exit("test")

    #AYO:  PUT IT HERE

    for keygenOutput_ind in keygenOutput:
        blindKeygenOutputElement(keygenOutput_ind, varsToBlindList, varNamesForListDecls, keygenFuncName)

    secretKeyName = keygenSecVar

    removeAssignmentOfOrigKeygenSecretKeyName(secretKeyName, keygenFuncName)

    #if (len(varsToBlindList) != 0):
        #sys.exit("keygen.py completed without blinding all of the variables passed to it by transform.py.")

    SDLLinesForKeygen = []
    for nonListBlindingFactor in blindingFactors_NonLists:
        SDLLinesForKeygen.append(nonListBlindingFactor + " := random(ZR)\n")

    inputLineOfKeygenFunc = getLineNoOfInputStatement(keygenFuncName)

    appendToLinesOfCode(SDLLinesForKeygen, inputLineOfKeygenFunc + 1)
    updateCodeAndStructs()

    writeOutputLineForKeygen(secretKeyName, keygenFuncName)

    for index_listVars in range(0, len(varNamesForListDecls)):
        varNamesForListDecls[index_listVars] = varNamesForListDecls[index_listVars] + blindingSuffix + " := list\n"

    for blindingFactor_List in blindingFactors_Lists:
        varNamesForListDecls.append(blindingFactor_List + " := list\n")

    lineNoEndTypesSection = getEndLineNoOfFunc(TYPES_HEADER)
    appendToLinesOfCode(varNamesForListDecls, lineNoEndTypesSection)
    updateCodeAndStructs()



    #varsThatAreBlinded = {"c":["zz"], "d0":["yy"], "d1":["aa", "bb"]}
    transformNEW(mappingOfSecretVarsToBlindingFactors, secretKeyElements, config)



    #(varsToBlindList, rccaData) = (transform(varsThatAreBlinded))

    #printLinesOfCode()
    #sys.exit("test")

    #rcca(rccaData)

    existingDecOutInputLineNo = getLineNoOfInputStatement(decOutFunctionName)
    existingDecOutInputLineNo -= 1
    existingDecOutInputLine = getLinesOfCode()[existingDecOutInputLineNo]

    replacementBlindingFactorsLine = getBlindingFactorsLine()
    #replacementBlindingFactorsLine = replacementBlindingFactorsLine[0:(len(replacementBlindingFactorsLine) - 1)]
    newDecOutInputLine = existingDecOutInputLine.replace(transformOutputList + "}", transformOutputList + ", " + replacementBlindingFactorsLine + "}", 1)

    substituteOneLineOfCode(newDecOutInputLine, existingDecOutInputLineNo + 1)

    updateCodeAndStructs()

    printLinesOfCode()

    #print(newDecOutInputLine)
    #sys.exit("TESTTEST")

    return (getLinesOfCode(), blindingFactors_NonLists, blindingFactors_Lists)

if __name__ == "__main__":
    keygen(sys.argv[1])
