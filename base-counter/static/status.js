var source = new EventSource("/status")
source.onmessage = function (event) {
	document.getElementById("base-count").innerHTML = event.data
}
