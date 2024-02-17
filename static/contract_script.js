 function upContract(id, button){

        // dostat jednotlivé proměnné
        var id, name, note, glue, cut, endDate
        contract = button.parentElement.parentElement

        id = contract.cells[1]
        name = contract.cells[2]
        note = contract.cells[3]
        cut = contract.cells[4].firstElementChild
        glue = contract.cells[4].lastElementChild
        dateCell = contract.cells[6]
        endDate = contract.cells[6].innerHTML.split("/")[1].split('.')

        idValue = id.firstChild.data
        nameValue = name.firstChild.data
        endDateValue = new Date().getFullYear()+'-'+endDate[1]+'-'+endDate[0].trim()


        if (note.firstChild == null){
            noteValue = ""
        } else {
            noteValue = note.firstChild.data
        }

        if (cut.getElementsByTagName("span")[0].innerHTML === 0){
            cutValue = "0"
        } else {
            cutValue = cut.getElementsByTagName("span")[0].innerHTML
        }

        if (glue.getElementsByTagName("span")[0].innerHTML.length === 0 ){
            glueValue = "0"
        }else{
            glueValue = glue.getElementsByTagName("span")[0].innerHTML
        }


        // Jednotlivé proměnné dostat do inputů, které poslouží jako výstup pro update
        name.innerHTML='<input class="form-control is-invalid" type="text" value="'+nameValue+'" name="name" onclick="setCursor(this)">'
        note.innerHTML='<textarea class="form-control is-invalid" type="textfield" name="note" onclick="setCursor(this)">'+noteValue+'</textarea>'
        cut.innerHTML='<input class="form-control is-invalid" type="number" value="'+cutValue+'" name="cut">'
        glue.innerHTML='<input class="form-control is-invalid" type="number" value="'+glueValue+'" name="glue">'
        dateCell.innerHTML='<input class="form-control is-invalid" type="date" value="'+endDateValue+'" name="date">'
        button.outerHTML='<button  onclick="updateRow(this)" class="btn btn-success btn-sm glyphicon glyphicon-ok"></button>'

    }

    function setCursor(input){
        this.scrollLeft = this.scrollWidth;
        input.setSelectionRange(input.value.length,input.value.length )
    }

    // Vlastní update
    function updateRow(row){
        var contractIndex, name, note, glue, cut, endDate


        contract = row.parentElement.parentElement
        contractIndex = contract.rowIndex-1

        name = contract.cells[2].querySelector('input').value.replace("/", " ")
        note = contract.cells[3].querySelector('textarea').value.replace("/", " ")
        cut = contract.cells[4].firstElementChild.querySelector('input').value
        glue = contract.cells[4].lastElementChild.querySelector('input').value
        date = contract.cells[6].querySelector('input').value

        $.get(`/update_row/${contractIndex}/${name}/${note}/${cut}/${glue}/${date}`, function() {
            location.reload();
        });
        
    }

 function myFunction() {
  var input, filter, table, tr, a, i, archive;
  input = document.getElementById("contractSearch");
  filter = input.value.toUpperCase();
  table = document.getElementById("listWithHandle");
  tr = table.getElementsByTagName("tr");
  for (i = 0; i < tr.length; i++) {
    a = tr[i].getElementsByTagName("td")[1];
    if (a.innerHTML.toUpperCase().indexOf(filter) > -1) {
      tr[i].style.display = "";
    } else {
      tr[i].style.display = "none";
    }
  }

  archive = document.getElementById("archivedContracts")
  archiveTr = archive.getElementsByTagName("tr");
  for (i = 0; i < archiveTr.length; i++) {
    a = archiveTr[i].getElementsByTagName("td")[1];
    if (a.innerHTML.toUpperCase().indexOf(filter) > -1) {
      archiveTr[i].style.display = "";
    } else {
      archiveTr[i].style.display = "none";
    }
  }

}

$( function() {
  $( "#task-list" ).sortable();
});

Sortable.create(listWithHandle, {
  handle: '#move',
  animation: 150
});

        function completeContract(contractIndex) {
            $.get(`/complete_contract/${contractIndex}`, function() {
                location.reload();
            });
        }

        function setFunction(contractIndex, button) {
            var inputField = button.parentNode.previousElementSibling;
            var inputValue = inputField.value;
            var inputName = inputField.name;
            $.get(`/set_value/${contractIndex}/${inputValue}/${inputName}`, function() {
                location.reload();
            });
        }

        function printContract(contractIndex) {
            string = 'print_pdf/'+contractIndex
            $.post(`/print_pdf/${contractIndex}`, function(){
                window.open(string, '_blank')
            });
        }

        function clearFunction(contractIndex, button) {
            var buttonName = button.name;
            $.get(`/clear_value/${contractIndex}/${buttonName}`, function() {
                location.reload();
            });
        }

        function setContractId(button) {
            var inputField = button.parentNode.previousElementSibling;
            var newId = inputField.value;
            $.get(`/set_contract_id/${newId}`, function() {
                location.reload();
            });
        }

        function setGlue(button) {
            var checkValue = button.value;
            $.get(`/set_glue/${checkValue}`, function(){
                location.reload();
            });
        }

        function setNumber() {
             ('/get_number', { method: 'POST' })
        }

        function updateContractOrder() {
            var taskList = document.getElementById('listWithHandle');
            var items = Array.from(taskList.children);
            var newOrder = items.map(function (item) {
                return item.dataset.index;
            });

            $.ajax({
                url: '/update_contract_order',
                type: 'POST',
                data: { contract_order: newOrder },
                success: function () {
                    // Po úspěšném uložení můžete provést nějakou akci, například zobrazení zprávy o úspěchu.
                }
            });
            location.reload()
        }

