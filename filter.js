function RefreshFilters()
{
	let inputsList = document.getElementsByClassName("input");
	let outputsList = document.getElementsByClassName("output");
	let hideTable = {"graph-column": true};

	for (let n = 0; n < inputsList.length; n++)
	{
		hideTable[inputsList[n].value] = inputsList[n].checked;
	}

	for (let n = 0; n < outputsList.length; n++)
	{
		hideTable[outputsList[n].value] = outputsList[n].checked;
	}

	let graphs = document.getElementsByClassName("graph-column");
	for (let n = 0; n < graphs.length; n++)
	{
		let graphClasses = graphs[n].classList;
		let reveal = true;
		for (let x = 0; x < graphClasses.length; x++)
		{
			reveal = reveal && hideTable[graphClasses[x]];
		}

		if (reveal)
		{
			graphs[n].setAttribute("style", "");
		}
		else
		{
			graphs[n].setAttribute("style", "display: none;");
		}
	}

}

function PageLoadInit()
{
	let checkboxList = document.getElementsByTagName("input");
	for (let n = 0; n < checkboxList.length; n++)
	{
		if (checkboxList[n].type === "checkbox")
		{
			checkboxList[n].setAttribute("onclick", "RefreshFilters()");
		}
	}
}

function TickAll(tickboxClass, shouldTick)
{
	let tickboxList = document.getElementsByClassName(tickboxClass);
	for (let n = 0; n < tickboxList.length; n++)
	{
		tickboxList[n].checked = shouldTick;
	}
	RefreshFilters();
}
