import React, {useState, useEffect} from 'react';
import Table from "./Table";
import Form from "./form";


  function MyApp() {
    const [characters, setCharacters] = useState([]);

    function fetchUsers() {
      const promise = fetch("http://localhost:8000/users");
      return promise;
    }

    useEffect(() => {
      fetchUsers()
        .then((res) => res.json())
        .then((json) => setCharacters(json["users_list"]))
        .catch((error) => { console.log(error); });
    }, [] );


    function removeOneCharacter(index) {
        const characterToRemove = characters[index];
        const characterId = characterToRemove.id; 
        
        fetch(`http://localhost:8000/users/${characterId}`, {
          method: 'DELETE'
        })
        .then(response => {
          if (response.status === 204) {
            const updated = characters.filter((character, i) => i !== index);
            console.log("here", updated)
            setCharacters(updated);
          } else {
            console.error('Failed to delete character:', response.statusText);
          }
        })
        .catch(error => {
          console.error('Error:', error);
        });
    }

    function postUser(person) {
      const promise = fetch("Http://localhost:8000/users", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(person),
      });
  
      return promise;
    }

    function updateList(person) { 
      postUser(person)
        .then(response => {
          if (response.status === 201) {
            response.json().then(insertedUser => {
              // Update state with the inserted user object
              setCharacters([...characters, insertedUser]);
            });
          } else {
            console.log("Failed to create user. Status code: ", response.status);
          }
        })
        .catch((error) => {
          console.log(error);
        })
    }

    return (
      <div className="container">
        <Table
          characterData={characters}
          removeCharacter={removeOneCharacter}
        />
        <Form 
          handleSubmit={updateList}
        />
      </div>
    );
  }

export default MyApp;